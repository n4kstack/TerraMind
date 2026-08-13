# Saved Models — Post-Symptom Diagnosis

This directory stores the trained model artifacts for the **Post-Symptom Diagnosis** module (TerraMind Model 3).

## Expected structure

```
saved_models/
└── trained_artifacts_fast/
    ├── class_metadata_fast.json                   # Class names, crop mapping, img_size — committed
    └── plant_disease_model_fast_torchscript.pt    # TorchScript export, primary inference — committed via LFS
```

Both files are committed, so the deployed Space can serve diagnoses. Only these
two are: `best_plant_disease_model_fast.pth` is the training-side checkpoint and
no inference path reads it, so `.gitignore` keeps its 14 MB out of the image.

## How to populate

Nothing to do for a normal clone — but clone *with* Git LFS, or run `git lfs
pull` afterwards. Without it the `.pt` stays a 133-byte pointer, `torch.jit.load`
fails, and `/api/v1/diagnosis/predict` answers `503 Diagnosis model is not
available`.

After retraining, copy the fresh `trained_artifacts_fast/` contents over these
files. Keep the `.gitignore` rule anchored as `/trained_artifacts_fast/` — written
bare it matches at every depth and silently re-excludes this directory, which is
exactly how the artifacts went missing from the Space before.

## Usage

The inference code in `ml/post_symptom_diagnosis/inference/model_wrapper.py` resolves this path automatically relative to the project root. **Do not use absolute paths.**
