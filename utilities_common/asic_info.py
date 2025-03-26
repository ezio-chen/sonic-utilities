from sonic_py_common import device_info

class AsicInfo:
    def __init__(self, platform):
        self.platform = platform if platform else ""

    @property
    def is_th(self):
        return self.asic_name == "th"

    @property
    def is_th2(self):
        return self.asic_name == "th2"

    @property
    def is_th3(self):
        return self.asic_name == "th3"

    @property
    def is_th4(self):
        return self.asic_name == "th4"

    @property
    def is_th5(self):
        return self.asic_name == "th5"

    @property
    def is_hr4(self):
        return self.asic_name == "hr4"

    @property
    def is_hx5(self):
        return self.asic_name == "hx5"

    @property
    def is_mv2(self):
        return self.asic_name == "mv2"

    @property
    def is_td2p(self):
        return self.asic_name == "td2+"

    @property
    def is_td3(self):
        return self.asic_name == "td3"

    @property
    def is_td4(self):
        return self.asic_name == "td4"

    @property
    def is_tf(self):
        return self.asic_name == "tf"

    @property
    def is_tf2(self):
        return self.asic_name == "tf2"

    @property
    def is_bf(self):
        return self.asic_name == "tf" or self.asic_name == "tf2"

    @property
    def is_bcm(self):
        return not self.is_bf

    @property
    def asic_name(self):
        if self.platform in [
                "x86_64-accton_as4625_54p-r0",
                "x86_64-accton_as4625_54t-r0",
        ]:
            return "hr4"

        if self.platform in [
                "x86_64-accton_as4630_54npe-r0",
                "x86_64-accton_as4630_54pe-r0",
                "x86_64-accton_as4630_54te-r0",
        ]:
            return "hx5"

        if self.platform in [
                "x86_64-accton_as5812_54t-r0",
                "x86_64-accton_as5812_54x-r0"
        ]:
            return "td2+"

        if self.platform in [
                "x86_64-accton_as5835_54t-r0",
                "x86_64-accton_as5835_54x-r0",
        ]:
            return "mv2"

        if self.platform in [
                "x86_64-accton_as7326_56x-r0",
                "x86_64-accton_as7726_32x-r0",
        ]:
            return "td3"

        if self.platform in ["x86_64-accton_as7712_32x-r0"]:
            return "th"

        if self.platform in [
                "x86_64-accton_as7816_64x-r0",
        ]:
            return "th2"

        if self.platform in [
                "x86_64-accton_as9716_32d-r0",
                "x86_64-accton_minipack-r0",
        ]:
            return "th3"

        if self.platform in [
                "x86_64-accton_as9726_32d-r0",
        ]:
            return "td4"

        if self.platform in [
                "x86_64-accton_as9736_64d-r0",
                "x86_64-accton_as9737_32db-r0",
        ]:
            return "th4"

        if self.platform in [
                "x86_64-accton_as9817_64d-r0",
                "x86_64-accton_as9817_64fk-r0",
                "x86_64-accton_as9817_64o-r0",
                "x86_64-accton_as9817_32d-r0",
                "x86_64-accton_as9817_32o-r0",
        ]:
            return "th5"

        if self.platform in [
                "x86_64-accton_wedge100bf_32qs-r0",
                "x86_64-accton_wedge100bf_32x-r0",
                "x86_64-accton_wedge100bf_65x-r0",
        ]:
            return "tf"

        if self.platform in [
                "x86_64-accton_as9516_32d-r0",
                "x86_64-accton_as9516bf_32d-r0 ",
        ]:
            return "tf2"

        return "unknown"


def get_asic_info():
    return AsicInfo(device_info.get_platform())
