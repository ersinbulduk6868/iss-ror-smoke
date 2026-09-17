#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender.iss_battle_runtime_contract import ActorProfile, BattleRuntimeContractError

EVIDENCE = ROOT / "docs/evidence/g03_bulldozer_production_ready_evidence.json"
ASSET_ADAPTER = ROOT / "blender/iss_battle_runtime_assets.py"
QUANT = ROOT / "assets/test-real-model/bulldozer_quant120.json"


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def profile(binding: dict, semantic_labels: tuple[str, ...]) -> ActorProfile:
    return ActorProfile.from_binding(binding, semantic_labels)


def main() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    source = evidence["sourceAsset"]
    ready = evidence["readyAsset"]
    interp = evidence["g03Interpretation"]

    check(source["status"] == "SOURCE_APPROVED", "G03_SOURCE_NOT_APPROVED")
    check(source["licenseCode"] == "CC_BY_4_0", "G03_LICENSE_NOT_VERIFIED")
    check(source["commercialUseAllowed"] is True, "G03_COMMERCIAL_USE_NOT_ALLOWED")
    check(source["modificationAllowed"] is True, "G03_MODIFICATION_NOT_ALLOWED")
    check(source["durableSourceUpload"] == "PASS", "G03_SOURCE_NOT_DURABLE")
    check(source["exactLicenseEvidenceGate"] == "PASS", "G03_LICENSE_EVIDENCE_MISSING")
    check(ready["status"] == "PRODUCTION_READY", "G03_READY_ASSET_NOT_PRODUCTION_READY")
    check(ready["sourceSha256Snapshot"] == source["sourceSha256"], "G03_SOURCE_READY_SHA_PROVENANCE_MISMATCH")
    check(ready["realNvidiaL4Acceptance"] is True, "G03_HISTORICAL_REAL_L4_ASSET_ACCEPTANCE_MISSING")
    check(ready["generationAssetLoadPass"] is True, "G03_GENERATION_ASSET_LOAD_PASS_MISSING")
    check(float(ready["totalMassKg"]) > 20000.0, "G03_DISSIMILAR_HEAVY_ASSET_MASS_NOT_PROVEN")
    check("blade" in ready["majorSemanticBodies"] and "track_left" in ready["majorSemanticBodies"], "G03_HEAVY_MACHINE_SEMANTICS_MISSING")

    # Same generic ActorProfile constructor handles radically different actor classes.
    hypercar = profile(
        {
            "entityId": "hypercar_probe",
            "massKg": 1450,
            "runtimeProfile": {
                "locomotionModel": "GROUND_DIFFERENTIAL",
                "maxSpeedMps": 20,
                "maxReverseMps": 6,
                "accelerationMps2": 7,
                "brakingMps2": 10,
                "maxYawRateRadS": 1.35,
                "toughnessJPerKg": 85,
            },
        },
        ("front", "rear", "body", "wheel"),
    )
    bulldozer = profile(
        {
            "entityId": "tracked_heavy_probe",
            "massKg": float(ready["totalMassKg"]),
            "runtimeProfile": {
                "locomotionModel": "GROUND_DIFFERENTIAL",
                "maxSpeedMps": 6.5,
                "maxReverseMps": 3.5,
                "accelerationMps2": 2.8,
                "brakingMps2": 4.0,
                "maxYawRateRadS": 0.55,
                "toughnessJPerKg": 180,
            },
        },
        tuple(ready["majorSemanticBodies"]),
    )
    check(hypercar.mass_kg != bulldozer.mass_kg, "G03_PROFILE_DIVERSITY_MISSING")
    check(bulldozer.max_speed_mps < hypercar.max_speed_mps, "G03_CAPABILITY_PROFILE_NOT_DISTINCT")
    check("blade" in bulldozer.semantic_labels and "track_left" in bulldozer.semantic_labels, "G03_TRACKED_SEMANTIC_PROFILE_MISSING")

    # Fail closed when physical identity required by runtime is absent/invalid.
    for bad in (
        {"entityId": "missing_mass"},
        {"entityId": "bad_mass", "massKg": 0},
        {"entityId": "nan_mass", "massKg": float("nan")},
    ):
        try:
            profile(bad, ())
        except (BattleRuntimeContractError, ValueError):
            pass
        else:
            raise RuntimeError("G03_INVALID_PROFILE_DID_NOT_FAIL_CLOSED")

    adapter = ASSET_ADAPTER.read_text(encoding="utf-8")
    low = adapter.lower()
    # Generic adapter source must not branch on fixture names.
    check("bugatti" not in low, "G03_ASSET_ADAPTER_BUGATTI_NAME_BRANCH")
    check("bulldozer" not in low, "G03_ASSET_ADAPTER_BULLDOZER_NAME_BRANCH")
    check(".glb" in adapter and ".gltf" in adapter and ".usd" in adapter, "G03_GENERIC_IMPORT_FORMAT_SUPPORT_MISSING")
    for marker in (
        "UNSUPPORTED_BLENDER_ASSET_FORMAT",
        "ACTOR_FORWARD_AXIS_UNRESOLVED",
        "ACTOR_NORMALIZED_DIMENSIONS_IMPLAUSIBLE",
        "VISIBLE_MESH_BOUNDS_MISSING",
    ):
        check(marker in adapter, f"G03_FAIL_CLOSED_MARKER_MISSING:{marker}")
    check("SEMANTIC_TERMS" in adapter and "CANONICAL_GEOMETRIC_ZONE" in adapter, "G03_GENERIC_SEMANTIC_DERIVATION_MISSING")

    # Existing exact-upload-derived real bulldozer surface evidence is useful
    # cross-check evidence but is deliberately NOT substituted for the full source.
    quant = json.loads(QUANT.read_text(encoding="utf-8"))
    check(quant["source_sha256"] == "187f81c3c4638180fb8d82c5b2bbc7510f01bc970ee149713b2de993089f1e18", "G03_QUANT_SOURCE_SHA_DRIFT")
    check(quant["transport"] == "exact-upload-derived-quantized-surface-v1", "G03_QUANT_TRANSPORT_DRIFT")
    check(int(quant["kept_triangles"]) == 120, "G03_QUANT_TRIANGLE_EVIDENCE_DRIFT")

    check(interp["sameCurrentBlenderGenericOnboardingFullSourceImportProven"] is False, "G03_EVIDENCE_OVERCLAIMED_FULL_IMPORT")
    check(interp["gateClosureAllowedFromThisEvidenceAlone"] is False, "G03_EVIDENCE_OVERCLAIMED_CLOSURE")

    result = {
        "status": "PASS_SUPPORT_BOUNDARY_PARTIAL",
        "gate": "ISS-G03",
        "genericActorProfileSameCodeAcrossClasses": True,
        "genericAdapterAssetNameBranches": False,
        "unsupportedOrInvalidProfileFailsClosed": True,
        "genericSemanticDerivationPresent": True,
        "dissimilarRealProductionAssetExists": True,
        "dissimilarAssetProductionReadyHistoricalEvidence": True,
        "dissimilarExactUploadDerivedGeometryEvidenceExists": True,
        "fullExactProductionBulldozerCurrentBlenderImport": False,
        "gateMachineClosureReady": False,
        "remainingExternalProof": "CURRENT_GENERIC_BLENDER_ADAPTER_FULL_EXACT_PRODUCTION_BULLDOZER_IMPORT",
        "remainingProofAccess": "GCS_OBJECT_REQUIRES_VERIFIED_ZERO_COST_OR_USER_APPROVED_BILLABLE_ACCESS",
        "noPerAssetBattleSourceCode": True,
        "productionAssetSourceSha256": source["sourceSha256"],
        "productionAssetReadySha256": ready["readySha256"],
        "productionAssetMassKg": ready["totalMassKg"],
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
