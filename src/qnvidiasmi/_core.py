import subprocess
import xml.etree.ElementTree as ET
import datetime as dt

class QNvidiaSmiXml:
    def __init__(self, root: ET.Element):
        self._root = root

    def parse(self, findstr: str, casttype: type):
        if (element:=self._root.find(findstr)) is not None and element.text is not None:
            return casttype(element.text)
        else:
            raise ValueError(f"{self.__class__.__name__}.{findstr} not found")


class QNvidiaSmiGPUState(QNvidiaSmiXml):
    def __init__(self, root: ET.Element):
        super().__init__(root)

    @property
    def root(self) -> ET.Element:
        return self._root

    @property
    def product_name(self) -> str:
        return self.parse("./product_name", str)

    @property
    def product_brand(self) -> str:
        return self.parse("./product_brand", str)

    @property
    def product_architecture(self) -> str:
        return self.parse("./product_architecture", str)

    @property
    def display_mode(self) -> bool:
        return self.parse("./display_mode", str) == "Enabled"

    @property
    def display_active(self) -> bool:
        return self.parse("./display_active", str) == "Enabled"

    @property
    def persistence_mode(self) -> bool:
        return self.parse("./persistence_mode", str) == "Enabled"

    @property
    def addressing_mode(self) -> str:
        # TODO: i only see None here, not sure what other modes there are
        return self.parse("./addressing_mode", str)

    @property
    def serial(self) -> str:
        return self.parse("./serial", str)

    @property
    def uuid(self) -> str:
        return self.parse("./uuid", str)

    # ==================================================================
    # ==================== FRAME BUFFER MEMORY i.e. VRAM ===============
    # ==================================================================
    def parse_mem(self, findstr: str) -> int:
        unitmap = {
            "KiB": 1024,
            "MiB": 1024**2,
            "GiB": 1024**3,
            "TiB": 1024**4
        }
        m = self.parse(findstr, str)
        size = int(m.split(" ")[0])
        unit = m.split(" ")[1]
        return size * unitmap[unit]

    @property
    def fb_mem_total(self) -> int:
        return self.parse_mem("./fb_memory_usage/total")

    @property
    def fb_mem_reserved(self) -> int:
        return self.parse_mem("./fb_memory_usage/reserved")

    @property
    def fb_mem_used(self) -> int:
        return self.parse_mem("./fb_memory_usage/used")

    @property
    def fb_mem_free(self) -> int:
        return self.parse_mem("./fb_memory_usage/free")

    @property
    def vram_total(self) -> int:
        """Alias for fb_mem_total"""
        return self.fb_mem_total

    @property
    def vram_reserved(self) -> int:
        """Alias for fb_mem_reserved"""
        return self.fb_mem_reserved

    @property
    def vram_used(self) -> int:
        """Alias for fb_mem_used"""
        return self.fb_mem_used

    @property
    def vram_free(self) -> int:
        """Alias for fb_mem_free"""
        return self.fb_mem_free

    # ==================================================================
    # ==================== UTILIZATION =================================
    # ==================================================================
    @property
    def util_gpu_percent(self) -> int:
        return int(self.parse("./utilization/gpu_util", str)[:-1])

    @property
    def util_mem_percent(self) -> int:
        return int(self.parse("./utilization/memory_util", str)[:-1])

    @property
    def util_encoder_percent(self) -> int:
        return int(self.parse("./utilization/encoder_util", str)[:-1])

    @property
    def util_decoder_percent(self) -> int:
        return int(self.parse("./utilization/decoder_util", str)[:-1])

    @property
    def util_jpeg_percent(self) -> int:
        return int(self.parse("./utilization/jpeg_util", str)[:-1])

    @property
    def util_ofa_percent(self) -> int:
        return int(self.parse("./utilization/ofa_util", str)[:-1])

    # ==================================================================
    # ==================== TEMPERATURE =================================
    # ==================================================================
    def parse_temp(self, findstr: str) -> int | None:
        temp = self.parse(findstr, str)
        if temp == "N/A":
            return None
        else:
            return int(temp[:-1])

    @property
    def temp_gpu_celsius(self) -> int | None:
        return self.parse_temp("./temperature/gpu_temp")

    @property
    def temp_tlimit_celsius(self) -> int | None:
        return self.parse_temp("./temperature/gpu_temp_tlimit")

    @property
    def temp_max_threshold_celsius(self) -> int | None:
        return self.parse_temp("./temperature/gpu_temp_max_threshold")

    @property
    def temp_slow_threshold_celsius(self) -> int | None:
        return self.parse_temp("./temperature/gpu_temp_slow_threshold")

    @property
    def temp_max_gpu_threshold_celsius(self) -> int | None:
        return self.parse_temp("./temperature/gpu_temp_max_gpu_threshold")

    @property
    def temp_target_celsius(self) -> int | None:
        return self.parse_temp("./temperature/gpu_target_temperature")

    @property
    def temp_memory_celsius(self) -> int | None:
        return self.parse_temp("./temperature/memory_temp")

    @property
    def temp_max_mem_threshold_celsius(self) -> int | None:
        return self.parse_temp("./temperature/gpu_temp_max_mem_threshold")


class QNvidiaSmiResult(QNvidiaSmiXml):
    def __init__(self, raw: str, isXml: bool):
        self._raw = raw
        if isXml:
            super().__init__(ET.fromstring(raw))

    @property
    def raw(self) -> str:
        return self._raw

    @property
    def root(self) -> ET.Element:
        return self._root

    @property
    def timestamp(self) -> dt.datetime:
        return dt.datetime.strptime(
            self.parse("./timestamp", str),
            # Day Mon Date Hour:Min:Sec Year
            "%a %b %d %H:%M:%S %Y"
        )

    @property
    def driver_version(self) -> str:
        return self.parse("./driver_version", str)

    @property
    def cuda_version(self) -> str:
        return self.parse("./cuda_version", str)

    @property
    def attached_gpus(self) -> int:
        return self.parse("./attached_gpus", int)

    @property
    def num_gpus(self) -> int:
        """
        Alias for attached_gpus.
        """
        return self.attached_gpus

    def __getitem__(self, idx: int) -> QNvidiaSmiGPUState:
        if idx < 0 or idx >= self.attached_gpus:
            raise IndexError(f"GPU index {idx} out of range (0-{self.attached_gpus-1})")
        return QNvidiaSmiGPUState(self._root.findall("./gpu")[idx])


class QNvidiaSmiExecutor:
    def __init__(self, exePath: str = "nvidia-smi"):
        self._exePath: str = exePath

    def query(self, options: list[str] | None = None) -> QNvidiaSmiResult:
        # If empty, just use "-q" as it gives most if not all information
        if options is None:
            options = ["-q"]

        # Enforce output as xml so it's easier to parse
        if "-x" not in options:
            options.append("-x")

        cmdline = [self._exePath, *options]
        result = subprocess.run(cmdline, capture_output=True, text=True)
        return QNvidiaSmiResult(result.stdout, True)


