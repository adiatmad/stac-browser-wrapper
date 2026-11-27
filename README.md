# STAC Browser Wrapper

A Streamlit application for working with STAC imagery metadata and preparing information for HOT OpenAerialMap (OAM) workflows.

## What it does

The application includes functionality for:

- resolving external STAC Browser URLs to their underlying STAC URLs;
- discovering public STAC catalogs and APIs from the OpenGeo geospatial-data-catalogs directory;
- querying STAC APIs through advertised GET Item Search links with optional WGS84 bbox, datetime, collection, and page-limit filters, capped at 1,000 items or 10 pages per search;
- showing thumbnail assets when a STAC Item explicitly advertises one;
- reading STAC item metadata;
- extracting imagery title, sensor, provider, dates, license, bounding box, and geometry information;
- checking OpenAerialMap for possible existing imagery using provider item IDs and spatial overlap;
- filtering STAC items spatially;
- preparing OAM-oriented metadata fields;
- displaying spatial information with Folium;
- discovering GeoTIFFs under public S3 Open Data prefixes;
- preparing OAM v2 remote-source handoffs without downloading the raster into the app;
- compressing local stitched orthomosaic GeoTIFFs into tiled, lossless ZSTD GeoTIFFs with GDAL, including validation and upload-size reporting;

## Requirements

Python 3 and the packages listed in requirements.txt.

## Run

    pip install -r requirements.txt
    streamlit run app.py

## OpenAerialMap compatibility

The OAM handoff follows the current [OAM uploader integration contract](https://github.com/hotosm/openaerialmap/blob/main/backend/uploader-api/README.md#integrating-an-external-system). Its documented fragment-prefill fields are title, provider, platform, license, acquisition_start, acquisition_end, sensor, contact, product_type, source_url, external_id, and external_url.

The current OAM STAC extension is [v0.3.0](https://docs.imagery.hotosm.org/oam/v0.3.0/schema.json). Its accepted license identifiers are CC-BY-4.0, CC-BY-SA-4.0, and CC-BY-NC-4.0. The uploader form uses display values such as CC-BY 4.0; its backend normalises these to the canonical identifiers. The local-file handoff uses the documented URL fragment but deliberately omits source_url: a Windows path is not a public URL and must never be sent to OAM as one.

For a remote import, source_url must be a public HTTPS URL that resolves directly to the GeoTIFF and remains valid through queueing and transfer. For a local file, choose Upload a file in the official uploader instead.

## Local GDAL command generator → OAM workflow

The **Local processing** tab generates commands for you to run in PowerShell. The app does not open, process, or upload your local imagery.

1. Enter the full path to the source GeoTIFF. The app suggests a separate `_oam.tif` output path.
2. Copy and run the generated `gdalinfo -json` command in PowerShell.
3. Copy the complete JSON output and paste it into the app.
4. The app checks the reported driver, dimensions, CRS, and geotransform, then generates a ready-to-copy `gdal_translate` command.
5. Run that command yourself. It creates a separate tiled ZSTD GeoTIFF using lossless compression, with no resampling, resizing, or JPEG. The generated PowerShell command first refuses to run if the output file already exists.

These are basic metadata checks, not a guarantee of OAM acceptance. ZSTD is an optional lossless optimization, not a mandatory OAM upload format. Compression may not reduce every file's size. Upload the resulting file manually using the official [OAM uploader](https://upload.imagery.hotosm.org/).


## Notes

The public catalog directory is sourced from [OpenGeo's geospatial-data-catalogs](https://github.com/opengeos/geospatial-data-catalogs) project and is loaded only when requested. API pagination follows GET links only and stops at the visible 1,000-item / 10-page safety cap. Its public-access flag describes catalog discovery, not the license or availability of every linked asset. The app does not infer licensing or bypass authentication. STAC API search uses only an advertised HTTPS GET search link and the core bbox, datetime, collections, and limit parameters; POST-only search and provider-specific extensions are not assumed.

The application communicates with external STAC and OAM services. Network availability and changes to those services can affect results.

## License

See LICENSE.

## AI-Assisted Development

This project was developed and/or maintained with AI assistance. AI was used to support parts of the design, implementation, documentation, and/or maintenance workflow. The human maintainer remains responsible for reviewing, validating, and approving the project's code and outputs.
