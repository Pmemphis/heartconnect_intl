"""Private, persistent image storage backed by Cloudinary."""
import time
import uuid
from pathlib import PurePosixPath
from urllib.request import urlopen

import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
import cloudinary.utils
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class CloudinaryPrivateImageStorage(Storage):
    """Upload profile images as private originals with short-lived URLs."""

    folder = 'heartconnect/profiles'

    def get_available_name(self, name, max_length=None):
        suffix = PurePosixPath(name).suffix.lower()
        return f'{self.folder}/{uuid.uuid4().hex}{suffix}'

    def _save(self, name, content):
        public_id = PurePosixPath(name).stem
        result = cloudinary.uploader.upload(
            content,
            resource_type='image',
            type='private',
            folder=self.folder,
            public_id=public_id,
            unique_filename=False,
            overwrite=False,
        )
        return f"{result['public_id']}.{result['format']}"

    @staticmethod
    def _parts(name):
        path = PurePosixPath(name)
        return str(path.with_suffix('')), path.suffix.lstrip('.')

    def url(self, name):
        public_id, file_format = self._parts(name)
        return cloudinary.utils.private_download_url(
            public_id,
            file_format,
            resource_type='image',
            type='private',
            expires_at=int(time.time()) + 600,
            attachment=False,
        )

    def exists(self, name):
        public_id, _ = self._parts(name)
        try:
            cloudinary.api.resource(public_id, resource_type='image', type='private')
        except cloudinary.exceptions.NotFound:
            return False
        return True

    def delete(self, name):
        public_id, _ = self._parts(name)
        cloudinary.uploader.destroy(
            public_id, resource_type='image', type='private', invalidate=True,
        )

    def _open(self, name, mode='rb'):
        with urlopen(self.url(name), timeout=20) as response:
            content = ContentFile(response.read(), name=name)
        return content
