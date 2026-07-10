# Molmo Download And Frontend Notes

This repository keeps Molmo as an external dependency instead of committing model weights.

Useful links:

- Molmo 7B-D Hugging Face model: https://huggingface.co/allenai/Molmo-7B-D-0924
- Molmo family collection: https://huggingface.co/collections/allenai/molmo-66f379e6fe3b8ef090a8ca19
- Official Molmo code: https://github.com/allenai/molmo
- Ai2 Molmo announcement: https://allenai.org/blog/molmo

Example download/cache command:

```bash
huggingface-cli download allenai/Molmo-7B-D-0924 --local-dir models/Molmo-7B-D-0924
```

Integration boundary:

- `semantic_grasping.frontend.MolmoFrontendAdapter` only defines the expected interface.
- For real runs, replace `predict_point(...)` with the Molmo/GraspMolmo code that returns a 2D task point such as `[u, v]`.
- Keep the output schema stable: task text, semantic point, optional confidence, raw model output path.
