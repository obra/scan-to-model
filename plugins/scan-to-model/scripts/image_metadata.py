"""Read non-destructive date metadata embedded in raster image bytes."""

from io import BytesIO

from PIL import ExifTags, Image


_DATE_FIELDS = {
    "original": (ExifTags.Base.DateTimeOriginal, ExifTags.Base.OffsetTimeOriginal),
    "digitized": (ExifTags.Base.DateTimeDigitized, ExifTags.Base.OffsetTimeDigitized),
    "modified": (ExifTags.Base.DateTime, ExifTags.Base.OffsetTime),
}


def read_exif_datetime_metadata(source_bytes):
    """Return embedded local-clock values without interpreting chronology or timezone.

    Date values are read from the EXIF sub-IFD where applicable.  An offset is
    reported only alongside its matching date field and remains ``None`` when
    absent; no UTC conversion or timezone inference is performed.
    """
    with Image.open(BytesIO(source_bytes)) as image:
        exif = image.getexif()
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
        result = {}
        for name, (date_tag, offset_tag) in _DATE_FIELDS.items():
            value = exif_ifd.get(date_tag, exif.get(date_tag))
            if value is None:
                continue
            offset = exif_ifd.get(offset_tag, exif.get(offset_tag))
            result[name] = {
                "local_clock": str(value),
                "offset": None if offset is None else str(offset),
            }
        return result
