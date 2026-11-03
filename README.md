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
- preparing OAM v2 remote-source handoffs without downloading the raster into the app;
- guiding local GeoTIFF preflight through copy-ready QGIS / OSGeo4W Shell commands and pasted GDAL reports.

## Requirements

Python 3 and the packages listed in requirements.txt.

## Run

    pip install -r requirements.txt
    streamlit run app.py

## OpenAerialMap compatibility

The OAM handoff follows the current [OAM uploader integration contract](https://github.com/hotosm/openaerialmap/blob/main/backend/uploader-api/README.md#integrating-an-external-system). Its documented fragment-prefill fields are title, provider, platform, license, acquisition_start, acquisition_end, sensor, contact, product_type, source_url, external_id, and external_url.

The current OAM STAC extension is [v0.3.0](https://docs.imagery.hotosm.org/oam/v0.3.0/schema.json). Its accepted license identifiers are CC-BY-4.0, CC-BY-SA-4.0, and CC-BY-NC-4.0. The uploader form uses display values such as CC-BY 4.0; its backend normalises these to the canonical identifiers. The local-file handoff uses the documented URL fragment but deliberately omits source_url: a Windows path is not a public URL and must never be sent to OAM as one.

For a remote import, source_url must be a public HTTPS URL that resolves directly to the GeoTIFF and remains valid through queueing and transfer. For a local file, choose Upload a file in the official uploader instead.

## Local geospatial imagery → OAM workflow

The Local preparation tab is report-driven. It works even when this Streamlit app is hosted because it never tries to open the user's local path or read raster bytes.

1. Paste the full raster path, for example D:\orthobekasigeotiff.tif.
2. Open QGIS / OSGeo4W Shell on the Windows computer that contains the file.
3. Run the generated GDAL version, JSON inspection, and PowerShell file-size commands.
4. Paste the JSON copied to the clipboard and the exact file size in bytes into the app.
5. Review the GDAL report and OAM checks: report-to-path match, affine georeferencing, dimensions, CRS, bands/types, per-band NoData, extent, compression, overviews, product type, decoded-size estimate, and the upstream default 100 GiB upload ceiling.
6. If the input is not a GeoTIFF or has no declared CRS, the app can generate a separate COG GeoTIFF command. It never guesses a CRS; -a_srs is included only after the user supplies a verified EPSG code. The command refuses to overwrite an existing output.
7. Paste the converted output path into the path field and repeat the report step before continuing.
8. Confirm the actual dataset title, imagery producer, platform, acquisition date, and accepted CC license. Open the official OAM uploader, select the local file yourself, review the prefilled values, sign in if prompted, and submit manually.

### What OAM actually requires

The current upstream uploader defaults to a **100 GiB** upload ceiling for GeoTIFF input; deployments can override this setting. Its processing pipeline then validates the raster, creates a COG, extracts metadata, and registers the STAC Item. A prebuilt local COG is therefore **not required** when the source is already a valid GeoTIFF with a CRS. The app offers local COG creation only as an optional copy for other workflows.

OAM's pipeline accepts visual, multispectral, SAR, elevation, and pseudocolor products. Three-band 8-bit imagery is detected as visual; a four-band image is only treated as visual when its fourth band is recognised as alpha. The pipeline keeps other products' native data and converts them losslessly. Eligible 8-bit RGB(A) visual imagery is converted to a JPEG quality-90 display COG; OAM retains the original upload separately.

The pipeline calculates GSD from the raster's pixel size and CRS and derives the published footprint from the raster mask or extent. The local handoff therefore does not ask the user to invent GSD or draw a STAC geometry. The acquisition date, producer, platform, title, and license still need human confirmation.

The decoded-size budget is deployment-configurable. Current upstream defaults are 130 GB for lossless conversion paths and approximately 216.7 GB for the eligible lossy visual path; the actual deployment may differ. The 100 GiB upload ceiling is separate from decoded size; treat it as the active default unless the OAM deployment operator confirms an override.

**Privacy and publication safeguards:** the user sends the pasted path, GDAL JSON report, and file size to the Streamlit app; the report may contain local paths and embedded metadata, so review it before pasting. Raster bytes remain on the user's computer. The OAM prefill URL contains metadata only, never a local path or local source_url. The app does not store OAM credentials, upload files, or publish imagery automatically.

## Notes

The application communicates with external STAC and OAM services. Network availability and changes to those services can affect results.

## License

See LICENSE.

## AI-Assisted Development

This project was developed and/or maintained with AI assistance. AI was used to support parts of the design, implementation, documentation, and/or maintenance workflow. The human maintainer remains responsible for reviewing, validating, and approving the project's code and outputs.
