"""Bounded prerequisite resolution for first-class Hades capabilities.

This is intentionally a small registry, not a general package-manager oracle.
Capabilities select prerequisites; the registry resolves only the packages
needed by those supported capabilities on a known platform.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import platform
import shutil
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class DependencyStatus(str, Enum):
    """Canonical prerequisite state; this is observation, not authority."""

    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    INSTALLABLE = "INSTALLABLE"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    UNSUPPORTED = "UNSUPPORTED"
    BROKEN = "BROKEN"
    VERSION_MISMATCH = "VERSION_MISMATCH"


class InstallationClass(str, Enum):
    CORE_IMAGE = "CORE_IMAGE"
    USER_SCOPED = "USER_SCOPED"
    HOST_PACKAGE = "HOST_PACKAGE"
    REMOTE_PACKAGE = "REMOTE_PACKAGE"
    CAPABILITY_GAP = "CAPABILITY_GAP"


@dataclass(frozen=True)
class DependencySpec:
    """A reviewed prerequisite declaration.

    Package names are platform mappings, never model-provided source URLs or
    shell fragments.  ``verification`` is descriptive contract metadata; the
    broker or transport adapter performs any actual verification.
    """

    dependency_id: str
    binary: str
    packages: Mapping[str, str] = MappingProxyType({})
    minimum_version: str | None = None
    installation_class: InstallationClass = InstallationClass.HOST_PACKAGE
    verification: tuple[str, ...] = ()
    source_policy: str = "approved_platform_repository"


@dataclass(frozen=True)
class DependencyDeclaration:
    capability_id: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class InstallerSpec:
    """Reviewed installation adapter metadata, not an executable command."""

    installer_id: str
    installation_class: InstallationClass
    backend_key: str
    supported_platforms: tuple[str, ...] = ()
    requires_approval: bool = True
    source_policy: str = "approved_platform_repository"


@dataclass(frozen=True)
class ArtifactSpec:
    """A downloadable/installable artifact with explicit provenance needs."""

    artifact_id: str
    kind: str
    source_policy: str
    resumable: bool = False
    credential_reference: str | None = None
    checksum_required: bool = False


@dataclass(frozen=True)
class RuntimeSpec:
    """A runtime projection over an artifact, never an arbitrary command."""

    runtime_id: str
    artifact_ids: tuple[str, ...]
    supported_platforms: tuple[str, ...]
    launch_backend: str
    verification_id: str
    endpoint_kind: str | None = None


@dataclass(frozen=True)
class VerificationSpec:
    """Evidence requirements for an installed artifact/runtime."""

    verification_id: str
    checks: tuple[str, ...]
    timeout_seconds: int = 15
    requires_provenance: bool = True


INSTALLER_REGISTRY: Mapping[str, InstallerSpec] = MappingProxyType({
    "installer.core_image": InstallerSpec("installer.core_image", InstallationClass.CORE_IMAGE, "release_image", ("linux", "windows", "macos"), False),
    "installer.user_pip": InstallerSpec("installer.user_pip", InstallationClass.USER_SCOPED, "cookbook_user_pip", ("linux", "windows", "macos"), False),
    "installer.host_package": InstallerSpec("installer.host_package", InstallationClass.HOST_PACKAGE, "privileged_broker", ("arch", "debian", "ubuntu")),
    "installer.remote_ssh": InstallerSpec("installer.remote_ssh", InstallationClass.REMOTE_PACKAGE, "canonical_ssh", ("linux", "windows", "macos")),
})

# Explicitly reviewed user-scoped distributions supported by the Cookbook
# adapter.  This is dependency metadata, not an instruction to invoke pip;
# execution remains in the existing route/venv adapter after normal admin and
# policy checks.  Keeping the allowlist here prevents UI routes from becoming
# a second package registry.
USER_SCOPED_PACKAGES = frozenset({
    "rembg[gpu]",
    "hf_transfer",
    "llama-cpp-python[server]",
    "sglang[all]",
    "diffusers",
    "diffusers[torch]",
    "git+https://github.com/huggingface/diffusers.git",
    "mflux",
    "git+https://github.com/xocialize/boogu-image-mlx.git",
    "mlx-vlm",
    "transformers",
    "TTS",
    "bark",
    "faster-whisper",
    "playwright",
    "realesrgan",
    "gfpgan",
    "insightface",
    "onnxruntime-gpu",
    "onnxruntime",
    "hdbscan",
    "vllm",
    "mlx-lm",
})

HOST_PACKAGE_ALLOWLIST = frozenset({
    "cmake", "build-essential", "g++", "gcc", "git", "tmux", "make", "nmap",
})

# Cookbook's reviewed semantic package names projected to each supported
# package-manager vocabulary. Values are data for the existing bounded shell
#/SSH adapter; this registry never constructs or runs a command.
HOST_PACKAGE_MAPPINGS: Mapping[str, Mapping[str, tuple[str, ...]]] = MappingProxyType({
    "apt": MappingProxyType({name: (name,) for name in HOST_PACKAGE_ALLOWLIST}),
    "pacman": MappingProxyType({
        **{name: (name,) for name in HOST_PACKAGE_ALLOWLIST if name != "build-essential"},
        "build-essential": ("base-devel",),
    }),
    "dnf": MappingProxyType({
        "cmake": ("cmake",), "build-essential": ("gcc", "gcc-c++", "make"),
        "g++": ("gcc-c++",), "gcc": ("gcc",), "git": ("git",),
        "tmux": ("tmux",), "make": ("make",), "nmap": ("nmap",),
    }),
    "apk": MappingProxyType({
        **{name: (name,) for name in HOST_PACKAGE_ALLOWLIST if name != "build-essential"},
        "build-essential": ("build-base",),
    }),
    "zypper": MappingProxyType({
        "cmake": ("cmake",), "build-essential": ("gcc-c++", "make"),
        "g++": ("gcc-c++",), "gcc": ("gcc",), "git": ("git",),
        "tmux": ("tmux",), "make": ("make",),
    }),
    "brew": MappingProxyType({
        name: ((name,) if name not in {"build-essential", "g++", "gcc", "make"} else ())
        for name in HOST_PACKAGE_ALLOWLIST
    }),
})


ARTIFACT_REGISTRY: Mapping[str, ArtifactSpec] = MappingProxyType({
    "artifact.huggingface_snapshot": ArtifactSpec("artifact.huggingface_snapshot", "model_snapshot", "huggingface_allowlisted_transport", resumable=True, credential_reference="secret://huggingface/token"),
    "artifact.ollama_model": ArtifactSpec("artifact.ollama_model", "ollama_model", "ollama_backend_transport", resumable=True),
    "artifact.python_distribution": ArtifactSpec("artifact.python_distribution", "python_distribution", "approved_package_index", resumable=True),
})


VERIFICATION_REGISTRY: Mapping[str, VerificationSpec] = MappingProxyType({
    "verify.binary": VerificationSpec("verify.binary", ("executable_present", "version_satisfies")),
    "verify.huggingface_snapshot": VerificationSpec("verify.huggingface_snapshot", ("cache_complete", "provenance_recorded"), 30),
    "verify.ollama_model": VerificationSpec("verify.ollama_model", ("model_listed", "endpoint_reachable"), 20),
    "verify.runtime_endpoint": VerificationSpec("verify.runtime_endpoint", ("endpoint_registered", "health_probe_passed"), 20),
})


RUNTIME_REGISTRY: Mapping[str, RuntimeSpec] = MappingProxyType({
    "runtime.ollama": RuntimeSpec("runtime.ollama", ("artifact.ollama_model",), ("linux", "windows", "macos"), "cookbook_ollama", "verify.ollama_model", "ollama"),
    "runtime.vllm": RuntimeSpec("runtime.vllm", ("artifact.huggingface_snapshot", "artifact.python_distribution"), ("linux", "windows"), "cookbook_vllm", "verify.runtime_endpoint", "openai_compatible"),
    "runtime.sglang": RuntimeSpec("runtime.sglang", ("artifact.huggingface_snapshot", "artifact.python_distribution"), ("linux", "windows"), "cookbook_sglang", "verify.runtime_endpoint", "openai_compatible"),
    "runtime.llama_cpp": RuntimeSpec("runtime.llama_cpp", ("artifact.huggingface_snapshot", "artifact.python_distribution"), ("linux", "macos", "windows"), "cookbook_llama_cpp", "verify.runtime_endpoint", "openai_compatible"),
    "runtime.mlx_lm": RuntimeSpec("runtime.mlx_lm", ("artifact.huggingface_snapshot", "artifact.python_distribution"), ("macos",), "cookbook_mlx", "verify.runtime_endpoint", "openai_compatible"),
})


class DependencyManager:
    """Canonical prerequisite backend shared by ACI and UI adapters.

    The manager is deliberately an observation/planning backend.  Existing
    Cookbook runners, the host broker, and the SSH adapter remain execution
    transports; none is duplicated here and this class never runs a command.
    """

    def inspect(self, capability_id: str, **kwargs: Any) -> dict[str, Any]:
        return inspect_capability_dependencies(capability_id, **kwargs)

    def inspect_one(self, dependency_id: str, **kwargs: Any) -> dict[str, Any]:
        return inspect_dependency(dependency_id, **kwargs)

    def inspect_action(self, binding: str, action_id: str, **kwargs: Any) -> dict[str, Any]:
        return inspect_action_dependencies(binding, action_id, **kwargs)

    def ensure_action(self, binding: str, action_id: str, **kwargs: Any) -> dict[str, Any]:
        """Build a bounded prerequisite plan for one canonical ActionSpec.

        This is deliberately a plan, not an installer.  The selected action
        remains the durable identity; a caller may hand the returned plan to
        the existing broker/SSH/Cookbook adapter and resume that same action
        after verification.  Unknown bindings/actions cannot manufacture
        package authority because ``inspect_action_dependencies`` only reads
        dependencies declared by the canonical registry.
        """
        target_asset = kwargs.pop("target_asset", None)
        inspected = self.inspect_action(binding, action_id, **kwargs)
        return _build_install_plan(
            inspected, target_asset=target_asset, resume_same_action=True,
        )

    def inspect_operation(self, operation_id: str, **kwargs: Any) -> dict[str, Any]:
        """Project the legacy operation view from canonical dependency data.

        Existing homelab/health callers use operation identifiers and a
        lowercase status vocabulary.  Keep that compatibility shape behind
        the shared manager so those callers do not become another inspection
        authority or registry.
        """
        return {**resolve(operation_id, **kwargs), "canonical_source": "DEPENDENCY_REGISTRY"}

    def resolve(self, capability_id: str, **kwargs: Any) -> dict[str, Any]:
        return ensure(capability_id, **kwargs)

    def ensure(self, capability_id: str, **kwargs: Any) -> dict[str, Any]:
        return ensure(capability_id, **kwargs)

    def verify(self, dependency_id: str, **kwargs: Any) -> dict[str, Any]:
        return verify(dependency_id, **kwargs)

    def plan_user_package(self, package: str) -> dict[str, Any]:
        """Validate one reviewed user-scoped package for the Cookbook adapter.

        The manager deliberately returns a contract projection only. It does
        not run pip, accept package URLs, or broaden the allowlist from model
        or retrieved text.
        """
        value = str(package or "").strip()
        if value not in USER_SCOPED_PACKAGES:
            return {
                "status": DependencyStatus.UNSUPPORTED.value,
                "package": value,
                "installation_class": InstallationClass.USER_SCOPED.value,
                "reason": "package_not_in_reviewed_allowlist",
            }
        installer = INSTALLER_REGISTRY["installer.user_pip"]
        return {
            "status": "READY_FOR_ADAPTER",
            "package": value,
            "installer_id": installer.installer_id,
            "backend": installer.backend_key,
            "installation_class": installer.installation_class.value,
            "source_policy": installer.source_policy,
            "pep668_safe": True,
            "venv_supported": True,
        }

    def plan_host_packages(self, packages: Iterable[object]) -> dict[str, Any]:
        """Project reviewed host package names for the existing broker adapter."""
        requested = [str(item).strip() for item in (packages or ()) if str(item).strip()]
        accepted = [item for item in requested if item in HOST_PACKAGE_ALLOWLIST]
        return {
            "status": "READY_FOR_ADAPTER" if accepted else DependencyStatus.UNSUPPORTED.value,
            "installation_class": InstallationClass.HOST_PACKAGE.value,
            "installer_id": "installer.host_package",
            "requested": accepted,
            "rejected": [item for item in requested if item not in HOST_PACKAGE_ALLOWLIST],
            "allowed_packages": sorted(HOST_PACKAGE_ALLOWLIST),
            "packages_by_manager": {
                manager: sorted({pkg for item in accepted for pkg in mapping.get(item, ())})
                for manager, mapping in HOST_PACKAGE_MAPPINGS.items()
            },
            "approval_required": True,
            "source_policy": INSTALLER_REGISTRY["installer.host_package"].source_policy,
        }

    def plan_remote_packages(
        self, packages: Iterable[object], *, target_asset: str | None,
    ) -> dict[str, Any]:
        """Project reviewed packages for the existing canonical SSH adapter.

        This is a contract projection only.  The remote transport still
        executes through its existing strict-SSH compatibility adapter until
        the full remote-package ActionSpec is migrated; package names and
        platform mappings remain owned here.
        """
        base = self.plan_host_packages(packages)
        target = str(target_asset or "").strip()
        if base.get("status") != "READY_FOR_ADAPTER" or not target:
            return {
                **base,
                "status": base.get("status") if base.get("status") != "READY_FOR_ADAPTER" else DependencyStatus.UNSUPPORTED.value,
                "reason": "remote_target_asset_required" if not target else base.get("reason", "unsupported_package"),
                "installation_class": InstallationClass.REMOTE_PACKAGE.value,
                "installer_id": "installer.remote_ssh",
                "target_asset": target or None,
            }
        return {
            **base,
            "installation_class": InstallationClass.REMOTE_PACKAGE.value,
            "installer_id": "installer.remote_ssh",
            "target_asset": target,
            "execution_authority": "canonical_ssh",
            "approval_required": True,
        }

    def resume_receipt(
        self,
        capability_id: str,
        *,
        run_id: str,
        action_id: str,
        approval_reference: str | None = None,
        platform_key: str | None = None,
    ) -> dict[str, Any]:
        """Bind prerequisite remediation to the original durable Action."""
        return remediation_handoff(
            capability_id,
            run_id=run_id,
            action_id=action_id,
            approval_reference=approval_reference,
            platform_key=platform_key,
        )

    def contracts(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "installers": [vars(item) | {"installation_class": item.installation_class.value} for item in INSTALLER_REGISTRY.values()],
            "artifacts": [vars(item) for item in ARTIFACT_REGISTRY.values()],
            "runtimes": [vars(item) for item in RUNTIME_REGISTRY.values()],
            "verification": [vars(item) for item in VERIFICATION_REGISTRY.values()],
            "dependencies": inspect_registry(),
        }


dependency_manager = DependencyManager()


class ArtifactManager:
    """Canonical artifact/runtime contract projection.

    Download and launch execution stays in the existing Cookbook, Ollama,
    SSH, and endpoint adapters.  This manager gives every caller one reviewed
    vocabulary and one place to validate that a requested runtime/artifact is
    known before handing off to those adapters.
    """

    def contracts(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "artifacts": [vars(item) for item in ARTIFACT_REGISTRY.values()],
            "runtimes": [vars(item) for item in RUNTIME_REGISTRY.values()],
            "verification": [vars(item) for item in VERIFICATION_REGISTRY.values()],
        }

    def artifact(self, artifact_id: str) -> ArtifactSpec | None:
        return ARTIFACT_REGISTRY.get(str(artifact_id or ""))

    def runtime(self, runtime_id: str) -> RuntimeSpec | None:
        return RUNTIME_REGISTRY.get(str(runtime_id or ""))

    def plan_artifact(self, artifact_id: str, *, source_reference: str | None = None) -> dict[str, Any]:
        spec = self.artifact(artifact_id)
        if spec is None:
            return {"status": "UNSUPPORTED", "artifact_id": artifact_id, "reason": "unknown_artifact"}
        # The source reference is intentionally opaque here.  The mature
        # adapter (HF/Ollama/package index) validates its own source syntax and
        # credentials before execution; this layer never turns it into shell.
        return {
            "status": "READY_FOR_ADAPTER",
            "artifact_id": spec.artifact_id,
            "kind": spec.kind,
            "source_policy": spec.source_policy,
            "source_reference": source_reference,
            "resumable": spec.resumable,
            "credential_reference": spec.credential_reference,
            "checksum_required": spec.checksum_required,
        }

    @staticmethod
    def _platform_key(value: str | None) -> str:
        """Normalize UI/host platform labels at the contract boundary."""
        normalized = str(value or platform.system()).strip().lower()
        return {"darwin": "macos", "mac": "macos", "android": "linux", "termux": "linux"}.get(normalized, normalized)

    def runtime_for_command(self, command: str | None) -> str | None:
        """Map known Cookbook launch commands to reviewed runtime identities.

        Unknown commands deliberately remain compatibility-adapter input.  The
        canonical backend must not guess that arbitrary shell is a trusted
        runtime or turn a model-provided command into authority.
        """
        text = str(command or "").lower()
        if "ollama" in text:
            return "runtime.ollama"
        if re.search(r"(?:^|\s)vllm(?:\s|$)", text):
            return "runtime.vllm"
        if re.search(r"(?:^|\s)sglang(?:\s|$)", text):
            return "runtime.sglang"
        if "llama-server" in text or "llama_cpp" in text or "llama-cpp-python" in text:
            return "runtime.llama_cpp"
        if "mlx_lm" in text or "mlx-lm" in text:
            return "runtime.mlx_lm"
        return None

    def plan_runtime(
        self,
        runtime_id: str,
        *,
        platform_key: str | None = None,
        source_references: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Validate a runtime request before handing off to mature adapters."""
        spec = self.runtime(runtime_id)
        if spec is None:
            return {"status": "UNSUPPORTED", "runtime_id": runtime_id, "reason": "unknown_runtime"}
        selected_platform = self._platform_key(platform_key)
        if selected_platform not in spec.supported_platforms:
            return {
                "status": "UNSUPPORTED",
                "runtime_id": spec.runtime_id,
                "platform": selected_platform,
                "reason": "unsupported_platform",
            }
        references = dict(source_references or {})
        artifacts = [
            self.plan_artifact(artifact_id, source_reference=references.get(artifact_id))
            for artifact_id in spec.artifact_ids
        ]
        if any(item["status"] != "READY_FOR_ADAPTER" for item in artifacts):
            return {
                "status": "UNSUPPORTED",
                "runtime_id": spec.runtime_id,
                "platform": selected_platform,
                "reason": "unsupported_artifact",
                "artifacts": artifacts,
            }
        verification = VERIFICATION_REGISTRY.get(spec.verification_id)
        return {
            "status": "READY_FOR_ADAPTER",
            "runtime_id": spec.runtime_id,
            "platform": selected_platform,
            "artifacts": artifacts,
            "launch_backend": spec.launch_backend,
            "endpoint_kind": spec.endpoint_kind,
            "verification_id": spec.verification_id,
            "verification": vars(verification) if verification else None,
            "authority": "existing_cookbook_adapter_through_canonical_policy",
        }

    def plan_runtime_for_command(
        self,
        command: str | None,
        *,
        platform_key: str | None = None,
        source_references: Mapping[str, str] | None = None,
    ) -> dict[str, Any] | None:
        runtime_id = self.runtime_for_command(command)
        if runtime_id is None:
            return None
        return self.plan_runtime(runtime_id, platform_key=platform_key, source_references=source_references)


artifact_manager = ArtifactManager()


_VERSION_RE = re.compile(r"\d+(?:\.\d+){0,3}")


@dataclass(frozen=True)
class CapabilityPrerequisite:
    """Compatibility view for callers that still use operation identifiers."""

    capability: str
    executables: tuple[str, ...]
    packages: dict[str, str]


# Canonical semantic prerequisite registry.  The compatibility ``REGISTRY``
# projection is built below from these specs; new callers should use the IDs
# below and the typed inspection functions.
DEPENDENCY_REGISTRY: Mapping[str, DependencySpec] = MappingProxyType({
    "binary.nmap": DependencySpec(
        "binary.nmap", "nmap", {"arch": "nmap", "debian": "nmap", "ubuntu": "nmap"},
        minimum_version="7.0",
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("nmap --version",),
    ),
    "binary.iproute2": DependencySpec(
        "binary.iproute2", "ip", {"arch": "iproute2", "debian": "iproute2", "ubuntu": "iproute2"},
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("ip -j addr", "ss -H -lnt"),
    ),
    "binary.ss": DependencySpec(
        "binary.ss", "ss", {"arch": "iproute2", "debian": "iproute2", "ubuntu": "iproute2"},
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("ss -H -lnt",),
    ),
    "binary.bind-utils": DependencySpec(
        "binary.bind-utils", "dig", {"arch": "bind", "debian": "bind9", "ubuntu": "bind9"},
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("dig -v",),
    ),
    "binary.host": DependencySpec(
        "binary.host", "host", {"arch": "bind", "debian": "bind9", "ubuntu": "bind9"},
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("host -V",),
    ),
    "binary.nslookup": DependencySpec(
        "binary.nslookup", "nslookup", {"arch": "bind", "debian": "bind9", "ubuntu": "bind9"},
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("nslookup -version",),
    ),
    "binary.traceroute": DependencySpec(
        "binary.traceroute", "traceroute", {"arch": "traceroute", "debian": "traceroute", "ubuntu": "traceroute"},
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("traceroute --version",),
    ),
    "binary.smartctl": DependencySpec(
        "binary.smartctl", "smartctl", {"arch": "smartmontools", "debian": "smartmontools", "ubuntu": "smartmontools"},
        installation_class=InstallationClass.HOST_PACKAGE,
        verification=("smartctl --version",),
    ),
})


# Compatibility declarations for callers that still name an operation rather
# than a registered Capability/ActionSpec. Registered actions are authoritative
# below; this map must not become a second dependency registry.
COMPATIBILITY_CAPABILITY_DEPENDENCIES: Mapping[str, DependencyDeclaration] = MappingProxyType({
    "network.discover_hosts": DependencyDeclaration("network.discover_hosts", ("binary.nmap",)),
    "network.context": DependencyDeclaration("network.context", ("binary.iproute2",)),
    "dns.resolve": DependencyDeclaration("dns.resolve", ("binary.bind-utils",)),
    "network.route_diagnostics": DependencyDeclaration("network.route_diagnostics", ("binary.traceroute",)),
    "storage.smart.inspect": DependencyDeclaration("storage.smart.inspect", ("binary.smartctl",)),
})


# The old operation names remain import-compatible, but their executable and
# package data is projected from the canonical typed registry above.  This is
# deliberately a mapping of IDs, not a second dependency/package registry.
_LEGACY_DEPENDENCY_IDS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "network_discovery": ("binary.nmap",),
    "network_interface_inspection": ("binary.iproute2", "binary.ss"),
    "dns_diagnostics": ("binary.bind-utils", "binary.host", "binary.nslookup"),
    "route_diagnostics": ("binary.traceroute",),
})


def _legacy_registry_projection() -> dict[str, CapabilityPrerequisite]:
    projected: dict[str, CapabilityPrerequisite] = {}
    for capability, dependency_ids in _LEGACY_DEPENDENCY_IDS.items():
        specs = [DEPENDENCY_REGISTRY[item] for item in dependency_ids if item in DEPENDENCY_REGISTRY]
        packages: dict[str, str] = {}
        # Legacy callers accept one package per platform.  All currently
        # projected binaries in a capability share their platform package;
        # retain the first reviewed value if a future declaration diverges.
        for spec in specs:
            for platform_key, package in spec.packages.items():
                packages.setdefault(platform_key, package)
        projected[capability] = CapabilityPrerequisite(
            capability,
            tuple(spec.binary for spec in specs),
            packages,
        )
    return projected


# Compatibility symbol only; canonical callers use DEPENDENCY_REGISTRY and
# ActionSpec.dependencies through the typed inspection APIs.
REGISTRY: dict[str, CapabilityPrerequisite] = _legacy_registry_projection()


def supported_capabilities() -> tuple[str, ...]:
    return tuple(sorted(REGISTRY))


def host_platform() -> str:
    """Return a deliberately small platform key from os-release."""
    configured = os.environ.get("HADES_HOST_PLATFORM", "").strip().lower()
    if configured in {"arch", "debian", "ubuntu"}:
        return configured
    values: dict[str, str] = {}
    try:
        for line in open("/etc/os-release", encoding="utf-8"):
            key, _, value = line.rstrip().partition("=")
            values[key] = value.strip('"')
    except OSError:
        pass
    ident = (values.get("ID") or "").lower()
    if ident in {"arch", "garuda", "manjaro", "endeavouros"}:
        return "arch"
    if ident in {"debian", "linuxmint", "pop"}:
        return "debian"
    if ident == "ubuntu":
        return "ubuntu"
    return ident or platform.system().lower()


def package_manager(platform_key: str | None = None) -> str | None:
    """Return the expected manager for the host platform.

    Hades itself may run in a container without the host package manager. The
    privileged broker performs the live manager check; planning must still be
    deterministic from the host-platform key.
    """
    key = platform_key or host_platform()
    return "pacman" if key == "arch" else "apt-get" if key in {"debian", "ubuntu"} else None


def package_manager_available(platform_key: str | None = None) -> bool:
    key = platform_key or host_platform()
    expected = package_manager(key)
    return bool(expected and shutil.which(expected))


def dependency_declarations(capability_id: str) -> tuple[DependencySpec, ...]:
    """Return reviewed prerequisites for one semantic capability."""
    declaration = COMPATIBILITY_CAPABILITY_DEPENDENCIES.get(str(capability_id or ""))
    if declaration is None:
        return ()
    return tuple(DEPENDENCY_REGISTRY[item] for item in declaration.dependencies if item in DEPENDENCY_REGISTRY)


def action_dependency_ids(binding: str, action_id: str) -> tuple[str, ...]:
    """Read prerequisites from the canonical Capability/ActionSpec contract.

    Tool bindings are only transport names. Resolving them here is a small
    adapter convenience; the dependency declaration remains on ActionSpec.
    Unknown bindings/actions deliberately return no dependencies so callers
    cannot manufacture installation authority from untrusted metadata.
    """
    from src.capability_registry import capability_for_tool

    capability = capability_for_tool(str(binding or ""))
    action = capability.actions.get(str(action_id or "")) if capability else None
    return tuple(action.dependencies) if action else ()


def _aggregate_dependency_status(items: Iterable[Mapping[str, Any]]) -> DependencyStatus:
    """Reduce prerequisite observations using one stable severity order."""
    statuses = {str(item.get("status") or "") for item in items}
    if not statuses or statuses == {DependencyStatus.AVAILABLE.value}:
        return DependencyStatus.AVAILABLE
    for status in (
        DependencyStatus.BROKEN.value,
        DependencyStatus.VERSION_MISMATCH.value,
        DependencyStatus.UNSUPPORTED.value,
        DependencyStatus.REQUIRES_APPROVAL.value,
        DependencyStatus.INSTALLABLE.value,
    ):
        if status in statuses:
            return DependencyStatus(status)
    return DependencyStatus.MISSING


def inspect_action_dependencies(
    binding: str,
    action_id: str,
    *,
    available_executables: Iterable[str] | None = None,
    versions: Mapping[str, str] | None = None,
    platform_key: str | None = None,
) -> dict[str, Any]:
    """Inspect the exact prerequisites declared by one canonical action."""
    from src.capability_registry import capability_for_tool

    capability = capability_for_tool(str(binding or ""))
    action = capability.actions.get(str(action_id or "")) if capability else None
    if action is None or not action.known:
        return {
            "binding": binding,
            "action_id": action_id,
            "status": DependencyStatus.UNSUPPORTED.value,
            "dependencies": [],
            "canonical_source": "ActionSpec.dependencies",
            "reason": "unknown_action",
        }
    dependency_ids = tuple(action.dependencies)
    items = [inspect_dependency(
        dependency_id,
        available_executables=available_executables,
        versions=versions,
        platform_key=platform_key,
    ) for dependency_id in dependency_ids]
    overall = _aggregate_dependency_status(items)
    return {
        "binding": binding,
        "action_id": action_id,
        "status": overall.value,
        "dependencies": items,
        "canonical_source": "ActionSpec.dependencies",
    }


def inspect_registry() -> list[dict[str, Any]]:
    """Project the dependency registry without executable or secret data."""
    return [
        {
            "dependency_id": spec.dependency_id,
            "binary": spec.binary,
            "packages": dict(spec.packages),
            "minimum_version": spec.minimum_version,
            "installation_class": spec.installation_class.value,
            "verification": list(spec.verification),
            "source_policy": spec.source_policy,
        }
        for spec in DEPENDENCY_REGISTRY.values()
    ]


def _version_tuple(value: str | None) -> tuple[int, ...] | None:
    if not value:
        return None
    match = _VERSION_RE.search(str(value))
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def inspect_dependency(
    dependency_id: str,
    *,
    available_executables: Iterable[str] | None = None,
    versions: Mapping[str, str] | None = None,
    platform_key: str | None = None,
    verification_error: str | None = None,
) -> dict[str, Any]:
    """Inspect one prerequisite deterministically.

    This function never invokes a package manager and never treats a model
    supplied URL, command, or package name as trusted input.
    """
    spec = DEPENDENCY_REGISTRY.get(str(dependency_id or ""))
    if spec is None:
        return {
            "dependency_id": dependency_id,
            "status": DependencyStatus.UNSUPPORTED.value,
            "reason": "unknown_dependency",
            "installation_class": InstallationClass.CAPABILITY_GAP.value,
        }
    key = platform_key or host_platform()
    manager = package_manager(key)
    package = spec.packages.get(key)
    available = set(available_executables) if available_executables is not None else None
    present = spec.binary in available if available is not None else bool(shutil.which(spec.binary))
    observed_version = None if versions is None else versions.get(spec.binary) or versions.get(spec.dependency_id)
    status = DependencyStatus.MISSING
    reason = "binary_not_found"
    if verification_error:
        status, reason = DependencyStatus.BROKEN, "verification_failed"
    elif present and spec.minimum_version and observed_version:
        required = _version_tuple(spec.minimum_version)
        observed = _version_tuple(observed_version)
        if required and observed and observed < required:
            status, reason = DependencyStatus.VERSION_MISMATCH, "minimum_version_not_met"
        else:
            status, reason = DependencyStatus.AVAILABLE, "binary_verified"
    elif present:
        status, reason = DependencyStatus.AVAILABLE, "binary_present"
    elif package and spec.installation_class is InstallationClass.USER_SCOPED:
        status, reason = DependencyStatus.INSTALLABLE, "approved_user_scoped_installation_available"
    elif package and spec.installation_class in {InstallationClass.HOST_PACKAGE, InstallationClass.REMOTE_PACKAGE}:
        status, reason = DependencyStatus.REQUIRES_APPROVAL, "bounded_package_install_requires_approval"
    elif spec.installation_class is InstallationClass.CORE_IMAGE:
        status, reason = DependencyStatus.MISSING, "dependency_must_be_in_release_image"
    else:
        status, reason = DependencyStatus.UNSUPPORTED, "no_reviewed_platform_mapping"
    return {
        "dependency_id": spec.dependency_id,
        "binary": spec.binary,
        "status": status.value,
        "reason": reason,
        "platform": key,
        "package_manager": manager,
        "package_manager_available": package_manager_available(key),
        "package": package,
        "packages": [package] if package else [],
        "installation_class": spec.installation_class.value,
        "minimum_version": spec.minimum_version,
        "observed_version": observed_version,
        "verification": list(spec.verification),
        "source_policy": spec.source_policy,
        "approval_required": status is DependencyStatus.REQUIRES_APPROVAL,
    }


def inspect_capability_dependencies(
    capability_id: str,
    *,
    available_executables: Iterable[str] | None = None,
    versions: Mapping[str, str] | None = None,
    platform_key: str | None = None,
) -> dict[str, Any]:
    """Inspect all declared dependencies for a capability."""
    declarations = dependency_declarations(capability_id)
    if not declarations:
        return {"capability": capability_id, "status": DependencyStatus.AVAILABLE.value, "dependencies": [], "reason": "no_declared_dependencies"}
    items = [inspect_dependency(
        item.dependency_id,
        available_executables=available_executables,
        versions=versions,
        platform_key=platform_key,
    ) for item in declarations]
    overall = _aggregate_dependency_status(items)
    return {"capability": capability_id, "status": overall.value, "dependencies": items}


def _build_install_plan(
    inspection: Mapping[str, Any], *, target_asset: str | None = None,
    resume_same_action: bool = False,
) -> dict[str, Any]:
    """Shape one bounded remediation plan for capability or ActionSpec input."""
    status = str(inspection.get("status") or DependencyStatus.MISSING.value)
    if status == DependencyStatus.AVAILABLE.value:
        return {**inspection, "action": "none", "resume_original_objective": False}
    if status not in {
        DependencyStatus.INSTALLABLE.value,
        DependencyStatus.REQUIRES_APPROVAL.value,
    }:
        return {**inspection, "action": "blocked", "resume_original_objective": False}
    packages = sorted({
        str(item["package"])
        for item in inspection.get("dependencies", ())
        if item.get("package")
    })
    return {
        **inspection,
        "action": (
            "install_user_scoped"
            if status == DependencyStatus.INSTALLABLE.value
            else "host_or_remote_package_install"
        ),
        "packages": packages,
        "target_asset": target_asset,
        "approval_required": status == DependencyStatus.REQUIRES_APPROVAL.value,
        "resume_original_objective": True,
        "resume_same_action": resume_same_action,
        "execution_authority": "canonical_broker_or_ssh_capability",
        "untrusted_sources_rejected": True,
    }


def ensure(
    capability_id: str,
    *,
    available_executables: Iterable[str] | None = None,
    versions: Mapping[str, str] | None = None,
    platform_key: str | None = None,
    target_asset: str | None = None,
) -> dict[str, Any]:
    """Create a bounded installation/resume plan; never perform installation."""
    result = inspect_capability_dependencies(
        capability_id,
        available_executables=available_executables,
        versions=versions,
        platform_key=platform_key,
    )
    return _build_install_plan(result, target_asset=target_asset)


def verify(
    dependency_id: str,
    *,
    observed_executables: Iterable[str],
    versions: Mapping[str, str] | None = None,
    platform_key: str | None = None,
    verification_ok: bool = True,
) -> dict[str, Any]:
    """Verify adapter/broker observations without executing arbitrary commands."""
    result = inspect_dependency(
        dependency_id,
        available_executables=observed_executables,
        versions=versions,
        platform_key=platform_key,
        verification_error=None if verification_ok else "verification_failed",
    )
    return {**result, "verified": result["status"] == DependencyStatus.AVAILABLE.value}


def resolve(capability: str, *, available: Iterable[str] | None = None, platform_key: str | None = None) -> dict:
    """Resolve missing executables to exact allowlisted package names."""
    spec = REGISTRY.get(str(capability or ""))
    if spec is None:
        return {"capability": capability, "status": "unavailable", "reason": "unsupported_capability", "remediation_available": False, "packages": []}
    present = set(available) if available is not None else {name for name in spec.executables if shutil.which(name)}
    missing = [name for name in spec.executables if name not in present]
    key = platform_key or host_platform()
    manager = package_manager(key)
    package = spec.packages.get(key)
    if not missing:
        status = "available"
    elif package and manager and package in _allowlisted_packages():
        status = "remediation_available"
    else:
        status = "unavailable"
    result = {
        "capability": spec.capability,
        "executables": list(spec.executables),
        "missing_executables": missing,
        "platform": key,
        "package_manager": manager,
        "package_manager_available": package_manager_available(key),
        "packages": [package] if package else [],
        "status": status,
        "remediation_available": status == "remediation_available",
    }
    return result


def _allowlisted_packages() -> frozenset[str]:
    # Import lazily to keep this registry usable by startup/read-only health.
    from src.privileged_broker import ALLOWED_PACKAGES
    return frozenset(ALLOWED_PACKAGES)


def capability_health(capability: str, *, available: Iterable[str] | None = None, platform_key: str | None = None) -> dict:
    return dependency_manager.inspect_operation(
        capability, available=available, platform_key=platform_key,
    )


def remediation_handoff(capability: str, *, run_id: str, action_id: str,
                        approval_reference: str | None = None,
                        platform_key: str | None = None) -> dict:
    """Create a durable, identity-preserving prerequisite handoff.

    This is metadata for the existing Work approval/resume engine. It never
    grants approval or executes a package manager. The original run/action
    identifiers are carried through install and verification so a caller
    cannot accidentally create a replacement run as a side effect.
    """
    # Existing homelab code names prerequisites by operation (for example
    # ``network_discovery``), while canonical ActionSpecs name semantic
    # capabilities (``network.discover_hosts``).  This is a compatibility
    # projection only; both names resolve to the same reviewed declaration.
    legacy_capability = str(capability or "")
    declaration = COMPATIBILITY_CAPABILITY_DEPENDENCIES.get(legacy_capability)
    if declaration and legacy_capability not in REGISTRY:
        first = declaration.dependencies[0] if declaration.dependencies else ""
        binary = DEPENDENCY_REGISTRY.get(first).binary if first in DEPENDENCY_REGISTRY else ""
        legacy_capability = next((name for name, item in REGISTRY.items() if binary in item.executables), legacy_capability)
    health = resolve(legacy_capability, available=[], platform_key=platform_key)
    if not health.get("remediation_available"):
        raise ValueError("no approved prerequisite remediation for capability")
    payload = {
        "capability": capability, "packages": health["packages"],
        "executables": health["executables"], "run_id": str(run_id),
        "action_id": str(action_id), "approval_reference": approval_reference,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {
        "kind": "prerequisite_remediation", "handoff_digest": sha256(canonical.encode()).hexdigest(),
        "resume_same_run": True, "resume_same_action": True, **payload,
        "capability_health": health,
    }
