'''
Package to query elevation information from SRTM 30m hgt
DEM elevation files via Python API or Web API

Copyright (C) Predly Technologies - All Rights Reserved
Marvin Gabler <m.gabler@predly.com> 2021

CREDIT: Code parts taken from: https://github.com/aatishnn/srtm-python
'''

import os
import sys
import gzip
import time
import numpy as np
from io import BytesIO
from shutil import copyfileobj
from boto3 import resource
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from botocore.handlers import disable_signing
from scipy.interpolate import griddata
import matplotlib.pyplot as plt

import asyncio
import aioredis


class OpenElevator():
    def __init__(self, initialized=False,cache=True):
        '''
        OpenElevator class for accessing elevation
        data programmatically

        Initialization:
            from open-elevator import OpenElevator

            elevator = OpenElevator()
            elevator.prepare_data()

        Example usage:
            from PIL import Image
            from openelevator import OpenElevator

            elevator = OpenElevator()
            
            # visualize a specific location
            img = elevator.plot_elevation( 0.44454, 12.34334)
            with Image.open(img) as im:
                im.show()

            # get elevation for specific location
            lat,lon = 0.44454, 12.34334
            print(elevator.get_elevation(lat,lon))
        '''
        # CONST
        self.AWS_ELEVATION_BUCKET="elevation-tiles-prod"
        self.AWS_HGT_DIR="skadi"
        self.SAMPLES=3601 # raster col/row size of dataset       
        self.INTERPOLATION_METHODS = [
            "none",
            "nearest",
            "linear",
            "cubic"
        ] # as available in skipy.interpolate.griddata
        self.COLORMAPS = [
            "terrain",
            "gist_earth",
            "ocean",
            "jet",
            "rainbow",
            "viridis",
            "cividis",
            "plasma",
            "inferno"
        ]

        # DIRS
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir    = os.path.join(self.current_dir, "data")
        self.temp_dir    = os.path.join(self.current_dir, "tmp")
        self.debug       = False

        # SYSTEM
        self.cpu_cores        = cpu_count()
        self.download_threads = self.cpu_cores if self.cpu_cores <= 16 else 16

        # CACHE
        self.cache_active = cache

        # INIT
        if initialized:
            if self.cache_active:
                self.cache = aioredis.from_url("redis://localhost", encoding="iso-8859-1", decode_responses=True)
        else:
            print("Initialize with self.prepare_data() or init class with initialized=True")
            

    def prepare_data(self, download=True):
        '''
        Download and preprocesses the neccessary DEM data from remote 
        s3:// repository to local tmp dir (self.temp_dir) with all available 
        processor threads. You need about 1.6 TB free space for the whole 
        extracted dataset.

        Workflow:
            1. Download data multithreaded
            2. Unzip data
            3. Place all files in data dir and delete zip files

        Args:
            download:bool >> Specify if data needs to be downloaded or is
                             already present in given self.temp_dir

                             You might already have downloaded the dataset
                             via s3 cli, so just place the data in a folder
                             called "tmp" in the working directory and start
                             with download=False to unzip the data and place
                             it in the data dir

                             command for aws cli:  
                                aws s3 cp --no-sign-request --recursive s3://elevation-tiles-prod/skadi /path/to/data/folder

        Returns:
            None
        '''
        
        if download:
            print("Initializing data download.")
            s3 = resource('s3')
            s3.meta.client.meta.events.register('choose-signer.s3.*', disable_signing)
            bucket = s3.Bucket(self.AWS_ELEVATION_BUCKET)
            key_list = [i.key for i in bucket.objects.filter(Prefix=self.AWS_HGT_DIR).all()]

            # create X download_threads times nested lists
            nested_size = int(len(key_list) / self.download_threads)
            download_list = [] 
            for i in range(self.download_threads):
                start = i * nested_size
                stop  = (i+1) * nested_size
                if i != (self.download_threads-1):  
                    download_list.append(key_list[start:stop])
                else:
                    download_list.append(key_list[start:])

            p = Pool(self.download_threads)
            print("Downloading",len(key_list), "files with", self.download_threads, "processes.\
                   This might take several hours depending on your connection.")
            p.map(self._download_single,download_list)
            p.close()

        # verify download and delete corrupted files
        data_subfolders = [os.path.join(self.temp_dir,i) for i in os.listdir(self.temp_dir)]
        p = Pool(self.cpu_cores)
        result_list_tqdm = []
        print("\nVerfying download and extracting files, working on", len(data_subfolders), "folders.")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        for result in tqdm(p.imap(func=self._verify_extract_single,
                        iterable=data_subfolders), total=len(data_subfolders)):
            result_list_tqdm.append(result) 
        p.close()
        # delete old folders
        for i in os.listdir(self.temp_dir):
            folder_path = os.path.join(self.temp_dir,i)
            try:
                os.rmdir(folder_path)
            except Exception as e:
                print(f"Directory {folder_path} not empty. Did not delete.")

    def _download_single(self, files):
        '''
        Downloads given s3 files from given AWS_ELEVATION_BUCKET

        This function is supposed to be multiprocessed and not
        being called directly.

        Args:
            files:list >> list of files with full path on AWS s3
        
        Returns:
            None
        '''

        s3 = resource('s3')
        s3.meta.client.meta.events.register('choose-signer.s3.*', disable_signing)
        bucket = s3.Bucket(self.AWS_ELEVATION_BUCKET)

        for idx, single_file in enumerate(files):
            local_path = single_file.replace("skadi",self.temp_dir)
            if not os.path.exists(os.path.dirname(local_path)):
                os.makedirs(os.path.dirname(local_path), exist_ok=True)            
            if not os.path.exists(local_path):
                if self.debug:
                    print(f"Downloading {single_file}")
                bucket.download_file(single_file,local_path)
            sys.stderr.write('\rdone {0:%} '.format(idx/len(files)))

    def _verify_extract_single(self, single_folder):
        '''
        Verifies downloaded files and and extracts gzipped files

        This function is to be multiprocessed and not being called
        directly.

        If the download has been stopped while in progress or any
        other error occured, there might be corrupted files or 'half files'.
        These wrong files are being deleted, while good files are being 
        extracted and placed in data folder.
        
        Args:
            single_folder:str >> folder in temp_dir to be checked
        
        Returns:
            None
        '''

        for j in os.listdir(single_folder):
            zip_file_path = os.path.join(single_folder,j)
            raw_file_path = os.path.join(
                self.data_dir, 
                os.path.basename(zip_file_path.replace(".gz", ""))
                )
            if ".gz." in j:
                os.remove(zip_file_path)
            else:
                if ".gz" in j:
                    with gzip.open(zip_file_path, "rb") as f_in:
                        with open(raw_file_path, "wb") as f_out:
                            copyfileobj(f_in, f_out)
                            os.remove(zip_file_path)

    def _get_file_name(self, lat, lon):
        """
        Returns filename such as N27E086.hgt, concatenated
        with HGTDIR as given by NASA's file syntax

        CREDIT: https://github.com/aatishnn/srtm-python
        
        Args:
            lat:float >> latitude, number between -90 and 90
            lon:float >> longitude, number between -180 and 180

        Returns:
            hgt_file:str >> name of hgt_file
                OR
            None
        """
        if lat >= 0:
            ns = 'N'
        elif lat < 0:
            ns = 'S'

        if lon >= 0:
            ew = 'E'
        elif lon < 0:
            ew = 'W'

        hgt_file = "%(ns)s%(lat)02d%(ew)s%(lon)03d.hgt" % \
                {'lat': abs(lat), 'lon': abs(lon), 'ns': ns, 'ew': ew}
        hgt_file_path = os.path.join(
            self.data_dir,
            hgt_file
            )

        if os.path.isfile(hgt_file_path):
            return hgt_file_path
        else:
            return None    

    def get_data_from_hgt_file(self, hgt_file):
        '''
        Get full data array from hgt file

        Hgt files are gridded binary files provided by NASA with
        a data type of 16bit signed integer(i2) - big endian(>).
        The data could also be read with rasterio or gdal, but takes
        a lot longer and would slow the workflow down. 

        Every file contains 3601x3601 values with an equal distance of
        1 arc seconds (30 meter).

        Args:
            hgt_file:str >> file_name of hgt file

        Returns:
            elevations:np.array >> 2d numpy array with 3601x3601 values

        '''
        with open(os.path.join(self.data_dir, hgt_file), 'rb') as hgt_data:            
            elevations = np.fromfile(
                hgt_data,  # binary data
                np.dtype('>i2'),  # data type
                self.SAMPLES * self.SAMPLES  # length
            ).reshape((self.SAMPLES, self.SAMPLES))
            return elevations

    async def get_elevation(self, lat, lon, interpolation="cubic"):
        """
        Get elevation for given lat,lon and interpolation method

        For locations between data points, interpolation is being used by
        scipy package. Interpolation methods available are cubic, linear and
        and nearest_neighbor. However, the underlying dataset is very accurate 
        (30 meter resolution), so the greatest distance to a verified measurement 
        is maximum 15 meters. 

        Args:
            lat:float >> latitude, number between -90 and 90
            lon:float >> longitude, number between -180 and 180
            interpolation:str >> interpolation_method in self.INTERPOLATION_METHODS
                                 ["none","linear","cubic","nearest"]
        
        Returns:
            elevation:float >> elevation above sea level
        """

        if interpolation not in self.INTERPOLATION_METHODS:
            print(f"Interpolation method {interpolation} not available. Available methods: {self.INTERPOLATION_METHODS}")
        else:
            hgt_file = self._get_file_name(lat, lon)
            if hgt_file:               

                lat_row = int(round((lat - int(lat)) * (self.SAMPLES - 1), 0))
                lon_row = int(round((lon - int(lon)) * (self.SAMPLES - 1), 0))
                lat_row_raw = (lat - int(lat)) * (self.SAMPLES - 1)
                lon_row_raw = (lon - int(lon)) * (self.SAMPLES - 1)   

                if self.cache_active:
                    cache_key = str(hgt_file) + "_" + str(lat_row_raw) + "_" + str(lon_row_raw) + "_" + interpolation
                    cache_result = await self.cache.get(cache_key)
                    if cache_result is not None:
                        return float(cache_result)

                elevations = self.get_data_from_hgt_file(hgt_file)                

                if interpolation == "none":                    
                    elevation = float(elevations[self.SAMPLES - 1 - lat_row, lon_row].astype(int))
                # in case we are at the very edges of a tile file, we do
                # not interpolate to avoid opening up to 4 tile files for
                # a single elevation lookup
                elif lat_row_raw == 0.0 or lon_row == 0.0:
                    elevation = float(elevations[self.SAMPLES - 1 - lat_row, lon_row].astype(int))
                else:
                    grid = [
                        [int(lon_row_raw), int(lat_row_raw)+1],
                        [int(lon_row_raw)+1, int(lat_row_raw)+1],
                        [int(lon_row_raw)+1, int(lat_row_raw)],
                        [int(lon_row_raw), int(lat_row_raw)]
                        ]
                    data = [
                        elevations[self.SAMPLES - 1 - int(lat_row_raw)+1, int(lon_row_raw)].astype(int),
                        elevations[self.SAMPLES - 1 - int(lat_row_raw)+1, int(lon_row_raw)+1].astype(int),
                        elevations[self.SAMPLES - 1 - int(lat_row_raw), int(lon_row_raw)+1].astype(int),
                        elevations[self.SAMPLES - 1 - int(lat_row_raw), int(lon_row_raw)].astype(int)
                    ]                  
                    elevation = float(griddata(
                        grid, data,
                        [lon_row_raw, lat_row_raw], 
                        method=interpolation
                        )[0])

                if self.cache_active:
                    await self.cache.set(cache_key, elevation)
                
                return elevation
            # Treat it as data void as in SRTM documentation
            # if file is absent
            return -32768

    def plot_elevation(self, lat, lon, colormap="terrain"):
        '''
        Plot elevation arround given coordinates and marks
        the coordinate location on the plot.

        For now, this function plots the hgt file, where the
        given coordinates are found on. For locations located
        at the edges, this solution is not great. This function
        was written mainly for development purposes.

        available colormaps:
            "terrain",
            "gist_earth",
            "ocean",
            "jet",
            "rainbow",
            "viridis",
            "cividis",
            "plasma",
            "inferno"

        Args:
            lat:float >> latitude, number between -90 and 90
            lon:float >> longitude, number between -180 and 180

        Returns:
            img:BytesIO memory buffer >> vizualize with
                                         >>from PIL import Image
                                         >>with Image.open(img) as f_img:
                                         >>    f_img.show()

        '''
        if colormap in self.COLORMAPS:
            hgt_file = self._get_file_name(lat, lon)
            if hgt_file:
                memory_buffer = BytesIO()
                data = self.get_data_from_hgt_file(hgt_file)
                lat_row = int(round((lat - int(lat)) * (self.SAMPLES - 1), 0))
                lon_row = int(round((lon - int(lon)) * (self.SAMPLES - 1), 0))

                plt.imshow(data, cmap=colormap)
                plt.title(f"Elevation arround lat {lat}, lon {lon}")
                plt.suptitle("Resolution: 1 arcsecond (30 meter)")
                plt.colorbar(label="meter above ground")
                plt.scatter(lon_row, lat_row, s=50, c='red', marker='x')

                plt.savefig(memory_buffer, format="png")            
                memory_buffer.seek(0)
                plt.clf()
                return memory_buffer
        else:
            print(f"colormap must be in {self.COLORMAPS}")

    def _dev_test_read_speed(self, set_cache=True):
        '''
        Development function to test read speed of hgt files
        '''
        start = time.time()
        lat, lon = 0.44454, 12.34334
        elevation = self.get_elevation(lat,lon)
        print(f"Height for lat {lat}, lon {lon} >> {elevation} << meter above ground")
        print("Took",(time.time()-start)*1000,"milliseconds")

if __name__ == "__main__":
    elevator = OpenElevator()
    if not os.path.exists("tmp"):
        if not os.path.exists("data"):
            elevator.prepare_data()
        else:
            if len(os.listdir(("data"))) == 0:
                elevator.prepare_data()
                