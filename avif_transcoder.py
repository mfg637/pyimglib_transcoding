import abc
import tempfile
import subprocess
import io
from . import webp_transcoder, config
from PIL import Image


class AVIF_WEBP_output(webp_transcoder.WEBP_output, metaclass=abc.ABCMeta):

    def _lossy_encode(self, img:Image.Image) -> None:
        src_tmp_file = None
        src_tmp_file_name = None
        if type(self._source) is str:
            src_tmp_file_name = self._source
        else:
            src_tmp_file = tempfile.NamedTemporaryFile(mode='wb', suffix=".png", delete=True)
            src_tmp_file_name = src_tmp_file.name
            img.save(src_tmp_file, format="PNG")
        #fix ICPP profiles error
        check_error = subprocess.run(['pngcrush', '-n', '-q', src_tmp_file_name], stderr=subprocess.PIPE)
        if b'pngcrush: iCCP: Not recognizing known sRGB profile that has been edited' in check_error.stderr:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            proc = subprocess.Popen(['convert', '-', src_tmp_file_name], stdin=subprocess.PIPE)
            proc.communicate(buf.getbuffer())
            proc.wait()
        alpha_tmp_file = None
        output_tmp_file = tempfile.NamedTemporaryFile(mode='rb', suffix=".avif", delete=True)
        if self._transparency_check(img):
            alpha_tmp_file = tempfile.NamedTemporaryFile(suffix=".avif", delete=True)
            subprocess.run([
                'cavif',
                '-i', src_tmp_file_name,
                '-o', alpha_tmp_file.name,
                '--encode-target', 'alpha',
                '--monochrome',
                '--lossless',
                '--cpu-used', '0',
                '--enable-full-color-range'
            ])
        commandline = [
            'cavif',
            '-i', src_tmp_file_name,
            '-o', output_tmp_file.name,
            '--encode-target', 'image'
        ]
        if alpha_tmp_file is not None:
            commandline += ['--attach-alpha', alpha_tmp_file.name]
        commandline += [
            '--crf', str(100 - self._quality),
            '--cpu-used', '0',
            '--profile', '1',
            '--pix-fmt', 'yuv444',
            '--enable-full-color-range',
            '--enable-cdef'
        ]
        if config.avif_encoding_threads is not None and config.avif_encoding_threads > 0:
            commandline += ['--enable-row-mt', '--threads', str(config.avif_encoding_threads)]
        subprocess.run(commandline)
        if alpha_tmp_file is not None:
            alpha_tmp_file.close()
        if src_tmp_file is not None:
            src_tmp_file.close()
        self._lossy_data = output_tmp_file.read()
        output_tmp_file.close()

    def _save_webp(self):
        if not self._lossless:
            self.file_suffix = ".avif"
        webp_transcoder.WEBP_output._save_webp(self)
