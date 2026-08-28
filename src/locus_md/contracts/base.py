from __future__ import annotations

from typing import Protocol

from ..models import ContractBinding, DocumentRecord, Finding, ManagedBlock, ProviderQuery, ProviderSnapshot


class ContractHandler(Protocol):
    api_version: str
    schema_id: str
    renderer_ids: frozenset[str]
    required_capabilities: frozenset[str]

    def plan(self, binding: ContractBinding, document: DocumentRecord, block: ManagedBlock) -> list[ProviderQuery]: ...

    def validate(self, binding: ContractBinding, document: DocumentRecord, block: ManagedBlock, snapshot: ProviderSnapshot) -> list[Finding]: ...

    def render(self, binding: ContractBinding, snapshot: ProviderSnapshot, newline: str) -> str: ...
