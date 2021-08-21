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
from redis import Redis
from shutil import copyfileobj
from boto3 import resource
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from botocore.handlers import disable_signing
from scipy.interpolate import griddata
import matplotlib.pyplot as plt


class OpenElevator():
    def __init__(self, initialized=False,cache=True):
        '''
        Notes:
            Downloading could be speeded up if using a shared
            client, but boto3 currently does not offer pickling
            of its ressources (https://github.com/boto/boto3/issues/2741)

        ToDos:
            - Init:
                - Check free space and raise error if <2TB
                - Dockerfile

        Initialization:
            from open-elevator import OpenElevator

            elevator = OpenElevator()
            elevator.prepare_data()

        Example usage:
            from PIL import Image
            from open-elevator import OpenElevator

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
                self.cache = Redis(host="localhost", port=6379, db=0)
        else:
            print("Initialize with self.prepare_data() or init class with initialized=True")
            

    def prepare_data(self, download=True):
        '''
        Download the neccessary DEM data to 
        tmp dir
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
        Downloads given s3 files 
        Function to multiprocess
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
        Checks and removes temp files 
        and extracts gzipped files
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
        with HGTDIR where these 'hgt' files are kept
        CREDIT: https://github.com/aatishnn/srtm-python
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
        '''
        with open(os.path.join(self.data_dir, hgt_file), 'rb') as hgt_data:
            # HGT is 16bit signed integer(i2) - big endian(>)
            elevations = np.fromfile(
                hgt_data,  # binary data
                np.dtype('>i2'),  # data type
                self.SAMPLES * self.SAMPLES  # length
            ).reshape((self.SAMPLES, self.SAMPLES))
            return elevations

    def get_elevation(self, lat, lon, interpolation="cubic"):
        """
        Get elevation for given lat,lon
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
                    cache_result = self.cache.get(cache_key)
                    if cache_result is not None:
                        return cache_result.decode("iso-8859-1")

                elevations = self.get_data_from_hgt_file(hgt_file)

                if interpolation == "none":                    
                    elevation = int(elevations[self.SAMPLES - 1 - lat_row, lon_row].astype(int))
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
                    self.cache.set(cache_key, elevation)
                
                return elevation
            # Treat it as data void as in SRTM documentation
            # if file is absent
            return -32768

    def plot_elevation(self, lat, lon, colormap="terrain"):
        '''
        Plot elevation arround given coordinates

        available colormaps:

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

    def dev_test_read_speed(self, set_cache=True):
        start = time.time()
        lat, lon = 0.44454, 12.34334
        if set_cache:
            elevation = self.get_elevation(lat,lon)
            self.cache.set((str(lat) + "_" + str(lon)), str(elevation))
        else:
            elevation = self.cache.get((str(lat) + "_" + str(lon))).decode("iso-8859-1")
        print(
            f"Height for lat {lat}, lon {lon} >> {elevation} << meter above ground")
        print("Took",(time.time()-start)*1000,"milliseconds")

if __name__ == "__main__":
    elevator = OpenElevator()
    elevator.prepare_data(download=False)