# Brand assets

The logo is the porter avatar alone, without a wordmark. The terminal mark on his cap and the pixel
glitch are part of the character.

| File | Use |
| --- | --- |
| `logo.svg` | Black avatar on a transparent background. |
| `logo-dark.svg` | White avatar on a transparent background. |
| `icon.svg` | Black avatar on a white rounded tile, visible in either theme. |
| `icon-128.png`, `icon-512.png`, `icon-1024.png` | Raster exports of `icon.svg` for plugin surfaces and avatars. |
| `avatar-source.png` | Transparent source artwork used to trace the SVG silhouette. |
| `how-it-works.svg`, `how-it-works-dark.svg` | Workflow diagram for light and dark themes. |
| `social-preview.svg`, `social-preview.png` | Avatar-only repository preview, 1280 by 640 pixels. |

The SVG artwork uses native paths, with no embedded bitmaps or external resources. Both diagram
variants have the same labels, approval rules and verification loop.

To export the plugin icons with Inkscape:

```sh
for size in 128 512 1024; do
  inkscape assets/icon.svg --export-filename="assets/icon-$size.png" \
    --export-width="$size" --export-height="$size"
done
inkscape assets/social-preview.svg --export-filename=assets/social-preview.png
```
