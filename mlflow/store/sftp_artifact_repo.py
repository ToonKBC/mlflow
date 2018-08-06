import os

from mlflow.entities.file_info import FileInfo
from mlflow.store.artifact_repo import ArtifactRepository
from mlflow.utils.file_utils import TempDir

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


class SFTPArtifactRepository(ArtifactRepository):
    """Stores artifacts as files in a remote directory, via sftp."""

    def __init__(self, artifact_uri, client=None):
        self.uri = artifact_uri
        parsed = urlparse(artifact_uri)
        self.config = {
            'host': parsed.hostname,
            'port': 22 if parsed.port is None else parsed.port,
            'username': parsed.username,
            'password': parsed.password
        }
        self.path = parsed.path
        # TODO read environment variables

        if client:
            self.sftp = client
        else:
            import pysftp
            import paramiko

            ssh_config = paramiko.SSHConfig()
            user_config_file = os.path.expanduser("~/.ssh/config")
            if os.path.exists(user_config_file):
                with open(user_config_file) as f:
                    ssh_config.parse(f)

            user_config = ssh_config.lookup(self.config['host'])
            if 'identityfile' in user_config:
                self.config['private_key'] = user_config['identityfile'][0]

            self.sftp = pysftp.Connection(**self.config)

        super(SFTPArtifactRepository, self).__init__(artifact_uri)

    def log_artifact(self, local_file, artifact_path=None):
        artifact_dir = os.path.join(self.path, artifact_path) \
            if artifact_path else self.path
        self.sftp.makedirs(artifact_dir)
        self.sftp.put(local_file, artifact_dir)

    def log_artifacts(self, local_dir, artifact_path=None):
        artifact_dir = os.path.join(self.path, artifact_path) \
            if artifact_path else self.path
        self.sftp.makedirs(artifact_dir)
        self.sftp.put_r(local_dir, artifact_dir)

    def list_artifacts(self, path=None):
        artifact_dir = self.path
        list_dir = os.path.join(artifact_dir, path) if path else artifact_dir
        artifact_files = self.sftp.listdir(list_dir)
        infos = []
        for file in artifact_files:
            file_path = file if path is None else os.path.join(path, file)
            full_file_path = os.path.join(list_dir, file)
            if self.sftp.isdir(full_file_path):
                infos.append(FileInfo(file_path, True, None))
            else:
                infos.append(FileInfo(file_path, False, self.sftp.stat(full_file_path).st_size))
        return infos

    def download_artifacts(self, path=None):
        artifact_path = os.path.join(self.path, path) \
            if path else self.path
        with TempDir(remove_on_exit=False) as tmp:
            tmp_path = tmp.path()
            if self.sftp.isdir(artifact_path):
                with self.sftp.cd(artifact_path):
                    self.sftp.get_r('.', tmp_path)
                return tmp_path
            else:
                local_file = os.path.join(tmp_path, os.path.basename(local_file))
                self.sftp.get(artifact_path, local_file)
                local_file