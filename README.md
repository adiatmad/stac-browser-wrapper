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

## Local GDAL preflight

The validator can consume either a raster directly or a saved `gdalinfo -json` report. The JSON path is useful when GDAL is available in QGIS/OSGeo4W but not on the current PowerShell `PATH`:

```bash
python validate_imagery.py validate-json gdalinfo.json
python validate_imagery.py recommend-json gdalinfo.json input.tif
```

Python's JSON parser is used for saved GDAL reports so metadata keys that PowerShell's `ConvertFrom-Json` may reject (including an empty key) do not block validation.

## Notes

The application communicates with external STAC and OAM services. Network availability and changes to those services can affect results.

## License

See [LICENSE](LICENSE).

## AI-Assisted Development

This project was developed and/or maintained with AI assistance. AI was used to support parts of the design, implementation, documentation, and/or maintenance workflow. The human maintainer remains responsible for reviewing, validating, and approving the project's code and outputs.
