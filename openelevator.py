'''
Package to query elevation information from SRTM 30m hgt
DEM elevation files via Python API or Web API

Marvin Gabler (c) 2021

CREDIT: Code parts taken from: https://github.com/aatishnn/srtm-python
'''

import os
import gzip
from shutil import copyfileobj
from boto3 import resource
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from botocore.handlers import disable_signing


class OpenElevator():
    def __init__(self):
        '''
        Notes:
            Downloading could be speeded up if using a shared
            client, but boto3 currently does not offer pickling
            of its ressources (https://github.com/boto/boto3/issues/2741)
        '''
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir    = os.path.join(self.current_dir, "data")
        self.temp_dir    = os.path.join(self.current_dir, "tmp")
        self.debug       = False

        # SYSTEM
        self.cpu_cores   = cpu_count()

        # CONST
        self.AWS_ELEVATION_BUCKET="elevation-tiles-prod"
        self.AWS_HGT_DIR="skadi"
        self.SAMPLE=3601 # raster col/row size

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

            p = Pool(self.cpu_cores)
            print("Downloading",len(key_list), "files with", self.cpu_cores, "processes.")
            result_list_tqdm = []
            for result in tqdm(p.imap(func=self._download_single,
                            iterable=key_list), total=len(key_list)):
                result_list_tqdm.append(result) 
            p.close()

        # verify download and delete corrupted files
        data_subfolders = [os.path.join(self.temp_dir,i) for i in os.listdir(self.temp_dir)]
        p = Pool(self.cpu_cores)
        result_list_tqdm = []
        print("Verfying download and extracting files, working on", len(data_subfolders), "folders.")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        for result in tqdm(p.imap(func=self._verify_extract_single,
                        iterable=data_subfolders), total=len(data_subfolders)):
            result_list_tqdm.append(result) 
        p.close()

    def _download_single(self, single_file):
        '''
        Downloads given s3 files 
        Function to multiprocess
        '''

        s3 = resource('s3')
        s3.meta.client.meta.events.register('choose-signer.s3.*', disable_signing)
        bucket = s3.Bucket(self.AWS_ELEVATION_BUCKET)

        local_path = single_file.replace("skadi",self.temp_dir)
        if not os.path.exists(os.path.dirname(local_path)):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)            
        if not os.path.exists(local_path):
            if self.debug:
                print(f"Downloading {single_file}")
            bucket.download_file(single_file,local_path)

    def _verify_extract_single(self, single_folder):
        '''
        Checks and removes temp files 
        and extracts gzipped files
        '''

        for j in os.listdir(single_folder):
            zip_file_path = os.path.join(single_folder,j)
            raw_file_path = os.path.join(self.data_dir, os.path.basename(zip_file_path.replace(".gz", "")))
            if ".gz." in j:
                os.remove(zip_file_path)
            else:
                if ".gz" in j:
                    with gzip.open(zip_file_path, "rb") as f_in:
                        with open(raw_file_path, "wb") as f_out:
                            copyfileobj(f_in, f_out)
                            os.remove(zip_file_path)

    def get_file_name(self, lat, lon):
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
        hgt_file_path = os.path.join(self.data_dir, hgt_file)
        if os.path.isfile(hgt_file_path):
            return hgt_file_path
        else:
            return None

    def get_elevation(self, lat, lon):
        """
        CREDIT: https://github.com/aatishnn/srtm-python
        """
        hgt_file = get_file_name(lat, lon)
        if hgt_file:
            return read_elevation_from_file(hgt_file, lat, lon)
        # Treat it as data void as in SRTM documentation
        # if file is absent
        return -32768

    def read_elevation_from_file(self, hgt_file, lat, lon):
        """
        CREDIT: https://github.com/aatishnn/srtm-python
        """
        with open(hgt_file, 'rb') as hgt_data:
            # HGT is 16bit signed integer(i2) - big endian(>)
            elevations = np.fromfile(
                hgt_data,  # binary data
                np.dtype('>i2'),  # data type
                SAMPLES * SAMPLES  # length
            ).reshape((SAMPLES, SAMPLES))

            lat_row = int(round((lat - int(lat)) * (SAMPLES - 1), 0))
            lon_row = int(round((lon - int(lon)) * (SAMPLES - 1), 0))

            return elevations[SAMPLES - 1 - lat_row, lon_row].astype(int)


if __name__ == "__main__":
    elevator = OpenElevator()
    elevator.prepare_data()