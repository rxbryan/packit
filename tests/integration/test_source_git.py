from packit.specfile import Specfile
from tests.integration.conftest import mock_spec_download_remote_s
from tests.spellbook import TARBALL_NAME, git_add_and_commit, build_srpm
    sourcegit_and_remote,
    distgit_and_remote,
    sourcegit, _ = sourcegit_and_remote
    distgit, _ = distgit_and_remote
    spec = Specfile(str(distgit / "beer.spec"))
    distgit_and_remote, mock_remote_functionality_sourcegit, api_instance_source_git
    distgit, _ = distgit_and_remote
    spec = Specfile(str(distgit / "beer.spec"))
    sourcegit_and_remote,
    distgit_and_remote,
    mock_remote_functionality_sourcegit,
    api_instance_source_git,
    sourcegit, _ = sourcegit_and_remote
    distgit, _ = distgit_and_remote
    spec = Specfile(str(distgit / "beer.spec"))