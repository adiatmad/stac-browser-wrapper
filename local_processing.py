"""Local lossless GeoTIFF compression helpers using GDAL CLI."""
from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path
from typing import Any
OAM_UPLOAD_LIMIT_BYTES = 100 * 1024**3
def _candidate_gdal_dirs() -> list[Path]:
    candidates=[]
    for env_name in ("OSGEO4W_ROOT","QGIS_PREFIX_PATH"):
        value=os.environ.get(env_name)
        if value:
            root=Path(value); candidates.extend([root/"bin",root/"apps"/"gdal"/"bin"])
            if env_name=="QGIS_PREFIX_PATH": candidates.extend([root.parent/"bin",root.parent/"apps"/"gdal"/"bin"])
    for root in (Path("C:/OSGeo4W"),Path("C:/OSGeo4W64")): candidates.extend([root/"bin",root/"apps"/"gdal"/"bin"])
    for base in (Path("C:/Program Files"),Path("C:/Program Files (x86)")):
        try:
            for qgis in base.glob("QGIS*"): candidates.extend([qgis/"bin",qgis/"apps"/"gdal"/"bin"])
        except OSError: pass
    return candidates
def find_gdal_tools() -> tuple[str|None,str|None]:
    info=shutil.which("gdalinfo") or shutil.which("gdalinfo.exe")
    translate=shutil.which("gdal_translate") or shutil.which("gdal_translate.exe")
    if info and translate: return info,translate
    for directory in _candidate_gdal_dirs():
        a,b=directory/"gdalinfo.exe",directory/"gdal_translate.exe"
        if a.is_file() and b.is_file(): return str(a),str(b)
    return info,translate
def _run(args:list[str])->subprocess.CompletedProcess[str]:
    try: return subprocess.run(args,check=True,capture_output=True,text=True,encoding="utf-8",errors="replace")
    except subprocess.CalledProcessError as exc:
        diagnostic=(exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(diagnostic or f"GDAL command failed (exit code {exc.returncode}).") from exc
def read_raster_info(gdalinfo_path:str,raster_path:str,checksums:bool=False)->dict[str,Any]:
    args=[gdalinfo_path,"-json"]
    if checksums: args.append("-checksum")
    args.append(raster_path); info=json.loads(_run(args).stdout)
    if not isinstance(info,dict) or not info.get("size") or not info.get("bands"): raise ValueError("GDAL did not return raster dimensions and bands for this file.")
    return info
def _image_structure(info:dict[str,Any])->dict[str,Any]: return ((info.get("metadata") or {}).get("IMAGE_STRUCTURE") or {})
def compression_command(gdal_translate_path:str,source:str,output:str,predictor:int=2)->list[str]:
    """Create tiled lossless ZSTD GeoTIFF. OAM builds the serving COG."""
    return [gdal_translate_path,"-of","GTiff","-co","TILED=YES","-co","BLOCKXSIZE=512","-co","BLOCKYSIZE=512","-co","COMPRESS=ZSTD","-co","ZSTD_LEVEL=9","-co",f"PREDICTOR={predictor}","-co","BIGTIFF=YES","-co","NUM_THREADS=ALL_CPUS",source,output]
def _compare_raster_structure(src:dict[str,Any],out:dict[str,Any])->list[str]:
    issues=[]
    for key,label in (("size","dimensions"),("geoTransform","geotransform")):
        if src.get(key)!=out.get(key): issues.append(f"Full-resolution {label} changed.")
    a,b=src.get("bands") or [],out.get("bands") or []
    if len(a)!=len(b): issues.append("Band count changed.")
    else:
        for i,(s,o) in enumerate(zip(a,b),1):
            for key,label in (("type","data type"),("colorInterpretation","color interpretation"),("noDataValue","NoData value")):
                if s.get(key)!=o.get(key): issues.append(f"Band {i} {label} changed.")
    ca,cb=src.get("coordinateSystem") or {},out.get("coordinateSystem") or {}
    if ca.get("id")!=cb.get("id") and ca.get("wkt")!=cb.get("wkt"): issues.append("Coordinate reference system changed or could not be matched.")
    if str(_image_structure(out).get("COMPRESSION","")).upper()!="ZSTD": issues.append("Output compression is not ZSTD.")
    if not b or not all(x.get("block") for x in b): issues.append("Output tiling could not be verified.")
    return issues
def process_lossless_geotiff(gdalinfo_path:str,gdal_translate_path:str,source_path:str,output_path:str,verify_checksums:bool=False)->dict[str,Any]:
    source,output=Path(source_path),Path(output_path)
    if not source.is_file(): raise ValueError("The source file does not exist or is not a file.")
    if source.resolve()==output.resolve(): raise ValueError("Choose a different output path; the original must never be overwritten.")
    if output.exists(): raise ValueError("Output already exists. Choose a new output filename; nothing was overwritten.")
    if source.suffix.lower() not in {".tif",".tiff"}: raise ValueError("Choose a stitched orthomosaic GeoTIFF (.tif or .tiff).")
    source_info=read_raster_info(gdalinfo_path,str(source),checksums=verify_checksums)
    if not source_info.get("coordinateSystem") or not source_info.get("geoTransform"): raise ValueError("Source is missing a CRS or geotransform. Correct it in QGIS first; compression cannot repair georeferencing.")
    bands=source_info.get("bands") or []; dtype=str(bands[0].get("type","")).lower()
    predictor=3 if dtype.startswith(("float","cfloat")) else 2
    command=compression_command(gdal_translate_path,str(source),str(output),predictor)
    try:
        _run(command); output_info=read_raster_info(gdalinfo_path,str(output),checksums=verify_checksums)
        issues=_compare_raster_structure(source_info,output_info)
        if verify_checksums:
            src_bands,out_bands=source_info.get("bands") or [],output_info.get("bands") or []
            if len(src_bands)!=len(out_bands) or any(x.get("checksum")!=y.get("checksum") for x,y in zip(src_bands,out_bands)): issues.append("Band checksums differ; pixel equality was not confirmed.")
    except Exception:
        if output.exists(): output.unlink()
        raise
    source_size,output_size=source.stat().st_size,output.stat().st_size
    return {"source_path":str(source),"output_path":str(output),"source_size_bytes":source_size,"output_size_bytes":output_size,"reduction_percent":(1-output_size/source_size)*100 if source_size else 0,"under_upload_limit":output_size<=OAM_UPLOAD_LIMIT_BYTES,"source_info":source_info,"output_info":output_info,"verification_issues":issues,"checksums_verified":verify_checksums and not any("checksum" in issue.lower() for issue in issues),"command":command}
