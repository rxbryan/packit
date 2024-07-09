# Copyright Contributors to the Packit project.
# SPDX-License-Identifier: MIT

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from osc import conf, core

from packit.config import PackageConfig
from packit.config.aliases import DEPRECATED_TARGET_MAP

logger = logging.getLogger(__name__)

_API_URL = "https://api.opensuse.org"


@dataclass(frozen=True)
class XmlPathEntry:
    """Representation of a path entry in the XML repository configuration of
    OBS.


    """

    project: str
    repository: str


@dataclass(frozen=True)
class Repository:
    """Minimal representation of a repository on OBS that is part of the project
    meta configuration:

    .. code-block:: xml

       <repository name="images">
         <path project="openSUSE:Factory" repository="containerfile"/>
         <path project="openSUSE:Factory" repository="standard"/>
         <arch>x86_64</arch>
       </repository>

    """

    name: str
    arch: list[str]
    path: list[XmlPathEntry]


def target_to_path(target: str) -> list[XmlPathEntry]:
    """Converts a packit target name like ``fedora-rawhide-x86_64`` or
    ``opensuse-leap-15.5`` to a list of xml path entries of the respective
    projects on OBS. This function relies on the project setup on
    build.opensuse.org and is not directly re-usable on other OBS instances.

    """

    target_split = target.split("-")
    version, arch = target_split[-2:]
    distro = "-".join(target_split[:-2])

    if distro == "fedora":
        if version == "rawhide":
            return [XmlPathEntry(project="Fedora:Rawhide", repository="standard")]
        return [
            XmlPathEntry(project=f"Fedora:{version}", repository="standard"),
            XmlPathEntry(project=f"Fedora:{version}", repository="update"),
        ]

    if distro == "epel":
        if version == "9":
            return [
                XmlPathEntry(project=f"Fedora:EPEL:{version}", repository="stream"),
            ]
        if version in ("8", "7"):
            return [
                XmlPathEntry(project=f"Fedora:EPEL:{version}", repository="CentOS"),
            ]

    if distro == "opensuse-leap":
        return [
            XmlPathEntry(project=f"openSUSE:Leap:{version}", repository="standard"),
        ]

    if distro == "opensuse":
        if arch == "x86_64":
            return [XmlPathEntry(project="openSUSE:Factory", repository="snapshot")]
        if arch in ("s390x", "aarch64", "ppc64le"):
            postfix = {"s390x": "zSystem", "aarch64": "ARM", "ppc64le": "PowerPC"}[
                arch
            ]
            return [
                XmlPathEntry(
                    project=f"openSUSE:Factory:{postfix}",
                    repository="standard",
                ),
            ]

    raise ValueError(f"No preset available for {distro=}, {version=}, {arch=}")

def targets_to_project_meta(
    targets: list[str],
    owner: str,
    project_name: str,
    description: Optional[str] = None,
) -> ET.Element:
    """Converts the list of packit targets (like `fedora-rawhide`) to a project
    meta xml configuration for the respective project in OBS.

    """
    repos: list[Repository] = []
    for target in targets:
        path = target_to_path(target)
        arch = target.split("-")[-1]
        name = target
        added = False

        for ind, repo in enumerate(repos):
            if repo.path == path:
                repos[ind] = Repository(
                    name=f"{repo.name}-{arch}",
                    path=path,
                    arch=[*repo.arch, arch],
                )
                added = True

        if not added:
            repos.append(Repository(name=name, path=path, arch=[arch]))

    root = ET.Element("project")
    root.attrib["name"] = project_name

    (title_elem := ET.Element("title")).text = "Packit project"
    (descr_elem := ET.Element("description")).text = description or ""
    (person_elem := ET.Element("person")).attrib["userid"] = owner
    person_elem.attrib["role"] = "maintainer"

    for elem in (title_elem, descr_elem, person_elem):
        root.append(elem)

    for repo in repos:
        (repo_elem := ET.Element("repository")).attrib["name"] = repo.name

        for path_entry in repo.path:
            (path_elem := ET.Element("path")).attrib["project"] = path_entry.project
            path_elem.attrib["repository"] = path_entry.repository
            repo_elem.append(path_elem)

        for arch in repo.arch:
            (arch_elem := ET.Element("arch")).text = arch
            repo_elem.append(arch_elem)

        root.append(repo_elem)

    return root

def create_package(project_name: str, package_name: str) -> None:
    """Creates the package with the name ``package_name`` in the project
    ``project_name`` on OBS. No sources are uploaded in the process.

    """
    (root := ET.Element("package")).attrib["name"] = package_name
    root.attrib["project"] = project_name

    (title := ET.Element("title")).text = f"The {package_name} package"
    descr = ET.Element("description")

    root.append(title)
    root.append(descr)

    package_url = core.makeurl(
        _API_URL,
        ["source", project_name, package_name, "_meta"],
    )
    metafile = core.metafile(package_url, ET.tostring(root))
    metafile.sync()

def create_obs_project(
    project: str,
    targets: str,
    owner: Optional[str],
    package_config: PackageConfig,
    description: Optional[str],
):
    conf.get_config()
    owner = owner or conf.config["api_host_options"][_API_URL]["user"]
    project_name = project or f"home:{owner}:packit"

    targets_list = targets.split(",")
    for target in targets_list:
        if target in DEPRECATED_TARGET_MAP:
            logger.warning(
                f"Target '{target}' is deprecated. "
                f"Please use '{DEPRECATED_TARGET_MAP[target]}' instead.",
            )

    project_metadata = targets_to_project_meta(
        targets=targets_list,
        owner=owner,
        project_name=project_name,
        description=description,
    )

    logger.info(f"Using OBS project name = {project_name}")

    project_url = core.makeurl(
        _API_URL,
        ["source", project_name, "_meta"],
    )
    metafile = core.metafile(project_url, ET.tostring(project_metadata))
    metafile.sync()

    package_names = list(package_config.packages.keys())

    if len(package_names) != 1:
        raise ValueError("Cannot handle multiple packages in package_config")

    create_package(project_name, (package_name := package_names[0]))

    return project_name, package_name

def init_project(
    build_dir: str,
    package_name: str,
    project_name: str,  # prj_str
) -> Path:
    core.Project.init_project(
        _API_URL,
        (prj_dir := Path(build_dir)),
        project_name,
    )

    (pkg_dir := (prj_dir / package_name)).mkdir()
    core.checkout_package(
        _API_URL,
        project_name,
        package_name,
        prj_dir=prj_dir,
        pathname=pkg_dir,
    )

    pkg = core.Package(pkg_dir)

    for fname in os.listdir(pkg_dir):
        pkg.delete_file(fname)

    return pkg_dir

def commit_srpm_and_get_build_results(
    srpm: Path,
    project_name: str,
    package_name: str,
    package_dir: Path,
    upstream_ref: Optional[str],
    wait: bool,
):
    # don't use the files argument of unpack_srcrpm, it allows for shell
    # injection unless sanitized carefully
    core.unpack_srcrpm(str(srpm), package_dir)

    core.addFiles(
        [
            str(package_dir / fname)
            for fname in filter(os.path.isfile, os.listdir(package_dir))
        ],
    )
    pkg = core.Package(package_dir)
    msg = "Created by packit"
    if upstream_ref:
        msg += f" from upstream revision {upstream_ref}"
    pkg.commit(msg=msg)

    # wait for the build result
    if wait:
        core.get_results(
            _API_URL,
            project_name,
            package_name,
            printJoin="",
            wait=True,
        )
