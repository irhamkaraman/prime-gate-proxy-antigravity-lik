from typing import Any, Dict, List, Optional, Set

UNSUPPORTED_CONSTRAINTS = [
    "minLength", "maxLength", "exclusiveMinimum", "exclusiveMaximum",
    "pattern", "minItems", "maxItems", "format", "default", "examples"
]

UNSUPPORTED_KEYWORDS = [
    *UNSUPPORTED_CONSTRAINTS,
    "$schema", "$defs", "definitions", "const", "$ref", "additionalProperties",
    "propertyNames", "title", "$id", "$comment"
]

EMPTY_PLACEHOLDER_NAME = "placeholder"
EMPTY_PLACEHOLDER_DESC = "Placeholder parameter for schemas without properties"

def append_description_hint(schema: Dict[str, Any], hint: str) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        return schema
    existing = schema.get("description", "")
    new_desc = f"{existing} ({hint})" if existing else hint
    return {**schema, "description": new_desc}

def convert_const_to_enum(schema: Any) -> Any:
    if isinstance(schema, list):
        return [convert_const_to_enum(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    res = {}
    for k, v in schema.items():
        if k == "const" and "enum" not in schema:
            res["enum"] = [v]
        else:
            res[k] = convert_const_to_enum(v)
    return res

def move_constraints_to_description(schema: Any) -> Any:
    if isinstance(schema, list):
        return [move_constraints_to_description(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    res = dict(schema)
    for c in UNSUPPORTED_CONSTRAINTS:
        if c in res and not isinstance(res[c], dict):
            res = append_description_hint(res, f"{c}: {res[c]}")
    for k, v in list(res.items()):
        if isinstance(v, (dict, list)):
            res[k] = move_constraints_to_description(v)
    return res

def merge_all_of(schema: Any) -> Any:
    if isinstance(schema, list):
        return [merge_all_of(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    res = dict(schema)
    if "allOf" in res and isinstance(res["allOf"], list):
        merged_props = {}
        merged_req: List[str] = []
        for item in res["allOf"]:
            if not isinstance(item, dict):
                continue
            if "properties" in item and isinstance(item["properties"], dict):
                merged_props.update(item["properties"])
            if "required" in item and isinstance(item["required"], list):
                for r in item["required"]:
                    if r not in merged_req:
                        merged_req.append(r)
            for k, v in item.items():
                if k not in ("properties", "required", "allOf") and k not in res:
                    res[k] = v
        if merged_props:
            res["properties"] = {**res.get("properties", {}), **merged_props}
        if merged_req:
            existing_req = res.get("required", [])
            res["required"] = list(dict.fromkeys(existing_req + merged_req))
        del res["allOf"]
    for k, v in list(res.items()):
        if isinstance(v, (dict, list)):
            res[k] = merge_all_of(v)
    return res

def flatten_any_of_one_of(schema: Any) -> Any:
    if isinstance(schema, list):
        return [flatten_any_of_one_of(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    res = dict(schema)
    for union_key in ["anyOf", "oneOf"]:
        if union_key in res and isinstance(res[union_key], list) and res[union_key]:
            options = res[union_key]
            parent_desc = res.get("description", "")
            # Pick first option or most structured option
            best_opt = options[0]
            if isinstance(best_opt, dict):
                selected = flatten_any_of_one_of(best_opt)
                if parent_desc:
                    selected = append_description_hint(selected, parent_desc)
                del res[union_key]
                res.update(selected)
                break
    for k, v in list(res.items()):
        if isinstance(v, (dict, list)):
            res[k] = flatten_any_of_one_of(v)
    return res

def remove_unsupported_keywords(schema: Any) -> Any:
    if isinstance(schema, list):
        return [remove_unsupported_keywords(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    res = {}
    for k, v in schema.items():
        if k in UNSUPPORTED_KEYWORDS:
            continue
        if k == "properties" and isinstance(v, dict):
            res["properties"] = {pk: remove_unsupported_keywords(pv) for pk, pv in v.items()}
        elif isinstance(v, (dict, list)):
            res[k] = remove_unsupported_keywords(v)
        else:
            res[k] = v
    return res

def cleanup_required_fields(schema: Any) -> Any:
    if isinstance(schema, list):
        return [cleanup_required_fields(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    res = dict(schema)
    if "required" in res and isinstance(res["required"], list):
        props = res.get("properties", {})
        if isinstance(props, dict):
            valid_req = [r for r in res["required"] if r in props]
            if valid_req:
                res["required"] = valid_req
            else:
                del res["required"]
    for k, v in list(res.items()):
        if isinstance(v, (dict, list)):
            res[k] = cleanup_required_fields(v)
    return res

def add_empty_schema_placeholder(schema: Any) -> Any:
    if isinstance(schema, list):
        return [add_empty_schema_placeholder(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    res = dict(schema)
    if res.get("type") == "object":
        props = res.get("properties")
        if not props or not isinstance(props, dict) or len(props) == 0:
            res["properties"] = {
                EMPTY_PLACEHOLDER_NAME: {
                    "type": "boolean",
                    "description": EMPTY_PLACEHOLDER_DESC
                }
            }
            res["required"] = [EMPTY_PLACEHOLDER_NAME]
    for k, v in list(res.items()):
        if isinstance(v, (dict, list)):
            res[k] = add_empty_schema_placeholder(v)
    return res

def clean_schema_for_antigravity(schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Complete sanitization pipeline for OpenAPI JSON schemas."""
    if not schema or not isinstance(schema, dict):
        return {
            "type": "object",
            "properties": {
                EMPTY_PLACEHOLDER_NAME: {
                    "type": "boolean",
                    "description": EMPTY_PLACEHOLDER_DESC
                }
            }
        }
    s = convert_const_to_enum(schema)
    s = move_constraints_to_description(s)
    s = merge_all_of(s)
    s = flatten_any_of_one_of(s)
    s = remove_unsupported_keywords(s)
    s = cleanup_required_fields(s)
    s = add_empty_schema_placeholder(s)
    return s
