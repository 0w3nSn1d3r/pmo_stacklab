# PMO StackLab

Interactive, pedagogical astrophotography image-stacking software.

PMO StackLab exposes every step and parameter of the image-stacking pipeline
(upload, calibrate, reproject, stack, post-process) through a web GUI, so that
students can experiment with algorithm and parameter choices, preview the
results, and learn how each decision affects the final image.

## Development

```
pip install -e .
python -m pmo_stacklab
```

Then open the URL printed by Flask (default http://127.0.0.1:5000/).
