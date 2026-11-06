# STAC Browser and imagery handoff

This glossary defines the geospatial and product language used by the STAC Browser Wrapper. It describes domain concepts, not code structure.

## STAC discovery and metadata

**STAC Catalog**: A JSON document that organizes links to STAC resources, including Collections and Items.  
_Avoid_: catalog API, unless referring specifically to an API endpoint.

**STAC Collection**: A logical grouping of related STAC Items with shared metadata and discovery context.

**STAC Item**: A GeoJSON feature describing one spatiotemporal asset or observation, with metadata and links to its assets.

**Asset**: A data file or related resource linked from a STAC Item, such as a thumbnail, preview, or source imagery.

**Item Search**: A STAC API capability advertised by a search link, used to query Items by supported parameters such as bbox, datetime, and collections.

## Imagery and OAM

**OpenAerialMap (OAM)**: HOT's platform for discovering and sharing openly licensed aerial imagery and associated metadata.

**OAM handoff**: A user-controlled transfer of prepared metadata or a public remote-source reference to the official OAM uploader. It is not an upload or publication by this app.

**Duplicate check**: A bounded lookup for an existing OAM Item using an exact provider Item ID and/or spatial overlap. An incomplete or failed lookup is not evidence that no duplicate exists.

**Local imagery preflight**: A report-driven check of a raster using metadata produced on the user's computer. The app receives the report, not the raster bytes.

**Cloud Optimized GeoTIFF (COG)**: A GeoTIFF organized to support efficient partial access over HTTP range requests. A COG is not automatically required for every local OAM upload.

## Safety language

**Public source URL**: An HTTPS URL accessible to the remote OAM service and resolving directly to the intended raster. A local filesystem path is never a public source URL.

**Verified CRS**: A coordinate reference system supported by trustworthy metadata or explicit user verification. The app must not infer or invent one.
