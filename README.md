# STAC Browser Wrapper

A Streamlit application for working with STAC imagery metadata and preparing information for HOT OpenAerialMap (OAM) workflows.

## What it does

The application includes functionality for:

- resolving external STAC Browser URLs to their underlying STAC URLs;
- reading STAC item metadata;
- extracting imagery title, sensor, provider, dates, license, bounding box, and geometry information;
- checking OpenAerialMap for possible existing imagery using provider item IDs and spatial overlap;
- filtering STAC items spatially;
- preparing OAM-oriented metadata fields;
- displaying spatial information with Folium;
- discovering GeoTIFFs under public S3 Open Data prefixes;
- preparing OAM v2 remote-source handoffs without downloading the raster into the app.

The application can use GDAL when available for server-side VRT-related processing, while the main application also works without the optional GDAL import.

## Requirements

Python 3 and the packages listed in `requirements.txt`.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## OpenAerialMap compatibility

The OAM handoff should follow the current [OAM uploader integration contract](https://github.com/hotosm/openaerialmap/blob/main/backend/uploader-api/README.md#integrating-an-external-system). Prefill links support `title`, `provider`, `platform`, `license`, `acquisition_start`, `acquisition_end`, `sensor`, `contact`, `product_type`, `source_url`, `external_id`, and `external_url`.

For OAM's current STAC extension, use the canonical Creative Commons identifiers `CC-BY-4.0`, `CC-BY-SA-4.0`, or `CC-BY-NC-4.0`; do not use a display-style value such as `CC-BY 4.0`. Keep `source_url` as a public HTTPS URL that resolves to the actual GeoTIFF, and only prefill acquisition dates when supported by source metadata.

## Local geospatial imagery workbench

The **Local preparation** workflow can inspect and prepare an existing raster with GDAL on the same computer that runs Streamlit:

1. Install GDAL through QGIS/OSGeo4W, or make `gdalinfo` and `gdal_translate` available on `PATH`.
2. Start this app locally (for example, from the QGIS/OSGeo4W shell): `streamlit run app.py`.
3. Paste the full path to an existing raster into **Source raster path** and click **Inspect raster**. The app checks whether the file is visible to the computer running Streamlit, discovers GDAL automatically, and reports any path or GDAL error. There is no GDAL-directory field.
4. Choose the actual OAM product type. Only `visual` requires 3–4 8-bit bands; multispectral, SAR, elevation, and pseudocolor products retain their native data type and band count.
5. If the raster passes the checks, create a separate lossless DEFLATE COG and (for visual RGB data) a downsampled PNG preview. The source is never overwritten. Existing output paths are refused.
6. Enter the known acquisition metadata and generate a local STAC/OAM JSON draft. Capture time, producer, GSD, platform, and license are not inferred.
7. Open the official OAM uploader with supported metadata prefilled, select the prepared COG (or original raster if you skipped preparation), re-enter GSD (the documented prefill contract does not include it), review, and submit there.

**Important:** A cloud-hosted Streamlit deployment cannot access your Windows files or local QGIS/GDAL installation. Run the app locally for this workflow. OAM performs its own server-side COG conversion after upload; the local COG is a lossless preparation copy, not a replacement for OAM's processing pipeline. The OAM prefill intentionally contains no local filesystem path or `source_url`, and this app does not store credentials or upload automatically.

The OAM uploader currently documents a 100 GiB file-upload ceiling. Its decoded-size validation is deployment-configurable; the workbench mirrors the current upstream default budget as a warning: 130 GB for lossless conversion paths, or about 216.7 GB for eligible 8-bit RGB/RGBA-with-alpha visual JPEG conversion. The deployed limit may differ.


## Notes

The application communicates with external STAC and OAM services. Network availability and changes to those services can affect results.

## License

See [LICENSE](LICENSE).

## AI-Assisted Development

This project was developed and/or maintained with AI assistance. AI was used to support parts of the design, implementation, documentation, and/or maintenance workflow. The human maintainer remains responsible for reviewing, validating, and approving the project's code and outputs.
