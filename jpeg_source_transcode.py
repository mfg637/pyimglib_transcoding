import abc
import subprocess
import struct
import os
from . import webp_transcoder, base_transcoder
from PIL import Image


is_arithmetic_SOF = {
    b'\xff\xc0': False,
    b'\xff\xc1': False,
    b'\xff\xc2': False,
    b'\xff\xc3': False,
    b'\xff\xc5': False,
    b'\xff\xc6': False,
    b'\xff\xc7': False,
    b'\xff\xc8': True,
    b'\xff\xc9': True,
    b'\xff\xca': True,
    b'\xff\xcb': True,
    b'\xff\xcd': True,
    b'\xff\xce': True,
    b'\xff\xcf': True
}


def is_arithmetic_jpg(file_path):
    file = open(file_path, 'rb')
    header = file.read(2)
    if header != b'\xff\xd8':
        file.close()
        raise OSError
    arithmetic = None
    marker = b"aaa"
    while len(marker):
        marker = file.read(2)
        if marker in is_arithmetic_SOF.keys():
            file.close()
            arithmetic = is_arithmetic_SOF[marker]
            return arithmetic
        elif len(marker):
            frame_len = struct.unpack('>H', file.read(2))[0]
            file.seek(frame_len - 2, 1)
    file.close()
    return None


class JPEGTranscode(webp_transcoder.WEBP_output):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _arithmetic_check(self):
        pass

    @abc.abstractmethod
    def _get_source_data(self):
        pass

    def _transparency_check(self, img: Image.Image) -> bool:
        return False

    def _apng_test_convert(self, img):
        pass

    def _all_optimisations_failed(self):
        pass

    def get_converter_type(self):
        return None

    def _encode(self):
        self._arithmetic_check()
        img = self._open_image()
        if (img.width>1024) or (img.height>1024):
            self._webp_output = True
            self._webp_encode(img)
        else:
            img.close()
            meta_copy = 'all'
            source_data = self._get_source_data()
            process = subprocess.Popen(['jpegtran', '-copy', meta_copy, '-arithmetic'],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            process.stdin.write(source_data)
            process.stdin.close()
            self._optimized_data = process.stdout.read()
            process.stdout.close()
            process.terminate()
            self._output_size = len(self._optimized_data)

    def _save(self):
        if self._webp_output:
            self._save_webp()
        else:
            outfile = open(self._output_file + ".jpg", 'wb')
            outfile.write(self._optimized_data)
            outfile.close()


class JPEGFileTranscode(base_transcoder.FilePathSource, base_transcoder.UnremovableSource, JPEGTranscode):
    def __init__(self, source: str, path: str, file_name: str, item_data: dict, pipe):
        base_transcoder.FilePathSource.__init__(self, source, path, file_name, item_data, pipe)
        base_transcoder.UnremovableSource.__init__(self, source, path, file_name, item_data, pipe)
        JPEGTranscode.__init__(self, source, path, file_name, item_data, pipe)
        self._quality = 100
        self._optimized_data = b''

    def _arithmetic_check(self):
        try:
            if is_arithmetic_jpg(self._source):
                raise base_transcoder.AlreadyOptimizedSourceException()
        except OSError:
            raise base_transcoder.NotOptimizableSourceException()

    def _get_source_data(self):
        source_file = open(self._source, 'br')
        raw_data = source_file.read()
        source_file.close()
        return raw_data

    def _set_utime(self) -> None:
        os.utime(self._source, (self._atime, self._mtime))

    def _optimisations_failed(self):
        pass

    def _invalid_file_exception_handle(self, e):
        print('invalid file ' + self._source + ' ({}) has been deleted'.format(e))
        os.remove(self._source)


class JPEGInMemoryTranscode(base_transcoder.InMemorySource, JPEGTranscode):
    def __init__(self, source:bytearray, path:str, file_name:str, item_data:dict, pipe):
        base_transcoder.InMemorySource.__init__(self, source, path, file_name, item_data, pipe)
        JPEGTranscode.__init__(self, source, path, file_name, item_data, pipe)
        self._quality = 100
        self._optimized_data = b''

    def _optimisations_failed(self):
        outfile = open(self._output_file + ".jpg", "bw")
        outfile.write(self._source)
        outfile.close()
        print("save " + self._output_file + ".jpg")

    def _arithmetic_check(self):
        pass

    def _get_source_data(self):
        return self._source

    def _invalid_file_exception_handle(self, e):
        print('invalid jpeg data')
