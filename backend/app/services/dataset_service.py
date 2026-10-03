import csv
import io
import math
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from app.config.settings import settings


def _normalize_column_name(name: str, index: int) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return f"column_{index + 1}"
    return cleaned


def _detect_encoding(raw_bytes: bytes) -> str:
    for candidate in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            raw_bytes.decode(candidate)
            return candidate
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _is_numeric_string(value: str) -> bool:
    if value is None:
        return False
    cleaned = value.strip().replace(",", "")
    if cleaned == "":
        return False
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _validate_csv_shape(sample: bytes, filename: str) -> None:
    if not filename:
        raise ValueError("A CSV file is required.")

    lower_name = filename.lower()
    if lower_name.endswith(".csv"):
        return

    content = sample[:4096].decode("utf-8", errors="ignore")
    if "," not in content and "\n" not in content:
        raise ValueError("Only CSV files are supported for Phase 3 dataset uploads.")


def validate_dataset_upload(file_name: str, content_type: str | None, sample: bytes) -> None:
    lower_name = (file_name or "").lower()
    lower_type = (content_type or "").lower()
    if lower_name.endswith(".csv") or "csv" in lower_type:
        return
    _validate_csv_shape(sample, file_name)


def analyze_csv_file(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise ValueError("Dataset file could not be found on disk.")

    with open(file_path, "rb") as handle:
        raw_data = handle.read()

    if not raw_data.strip():
        raise ValueError("Uploaded CSV is empty.")

    if len(raw_data) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"Dataset exceeds the configured upload size limit of {settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024):.1f} MB."
        )

    encoding = _detect_encoding(raw_data)
    try:
        text_content = raw_data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise ValueError("Dataset encoding could not be decoded. Please upload UTF-8 CSV data.") from exc

    validate_dataset_upload(os.path.basename(file_path), "text/csv", raw_data)

    reader = csv.reader(io.StringIO(text_content, newline=""))
    try:
        header_row = next(reader)
    except StopIteration as exc:
        raise ValueError("Uploaded CSV is empty.") from exc

    if not header_row or all((cell or "").strip() == "" for cell in header_row):
        raise ValueError("CSV header is missing or empty.")

    columns = [_normalize_column_name(column_name, index) for index, column_name in enumerate(header_row)]
    row_count = 0
    duplicate_row_count = 0
    seen_rows = set()
    missing_values: Dict[str, int] = {column: 0 for column in columns}
    unique_value_sets: Dict[str, set] = {column: set() for column in columns}
    malformed_rows = 0
    total_missing_cells = 0

    for row in reader:
        if len(row) != len(columns):
            malformed_rows += 1
            continue

        row_count += 1
        row_tuple = tuple(cell.strip() for cell in row)
        if row_tuple in seen_rows:
            duplicate_row_count += 1
        else:
            seen_rows.add(row_tuple)

        for index, cell in enumerate(row):
            column_name = columns[index]
            cell_value = cell.strip()
            if cell_value == "":
                missing_values[column_name] += 1
                total_missing_cells += 1
            else:
                unique_value_sets[column_name].add(cell_value)

    column_count = len(columns)
    if row_count == 0:
        quality_score = 0
        quality_status = "failed"
        findings: List[Dict[str, Any]] = [{
            "type": "empty_dataset",
            "severity": "error",
            "column": None,
            "message": "The uploaded file has a header but contains no data rows.",
            "value": 0,
        }]
        return {
            "row_count": 0,
            "column_count": column_count,
            "columns": columns,
            "missing_values": missing_values,
            "missing_percentages": {column: 0.0 for column in columns},
            "duplicate_rows": duplicate_row_count,
            "duplicate_percentage": 0.0,
            "unique_value_counts": {column: 0 for column in columns},
            "numeric_columns": [],
            "categorical_columns": columns,
            "inferred_types": {column: "empty" for column in columns},
            "quality_score": quality_score,
            "quality_status": quality_status,
            "status": quality_status,
            "findings": findings,
        }

    missing_percentages = {
        column: round((missing_values[column] / row_count) * 100, 2) if row_count else 0.0
        for column in columns
    }
    unique_value_counts = {
        column: len(unique_value_sets[column])
        for column in columns
    }
    duplicate_percentage = round((duplicate_row_count / row_count) * 100, 2) if row_count else 0.0

    inferred_types: Dict[str, str] = {}
    numeric_columns: List[str] = []
    categorical_columns: List[str] = []

    for column in columns:
        non_missing_values = [value for value in unique_value_sets[column] if value != ""]
        if not non_missing_values:
            inferred_types[column] = "empty"
            categorical_columns.append(column)
            continue

        if all(_is_numeric_string(value) for value in non_missing_values):
            inferred_types[column] = "numeric"
            numeric_columns.append(column)
        else:
            inferred_types[column] = "categorical"
            categorical_columns.append(column)

    findings: List[Dict[str, Any]] = []
    for column in columns:
        if missing_values[column] > 0:
            severity = "warning" if missing_percentages[column] < 25 else "error"
            findings.append({
                "type": "missing_values",
                "severity": severity,
                "column": column,
                "message": f"Column contains {missing_values[column]} missing values.",
                "value": missing_percentages[column],
            })

        if missing_values[column] == row_count:
            findings.append({
                "type": "empty_column",
                "severity": "error",
                "column": column,
                "message": "Column is completely empty.",
                "value": 100.0,
            })

        if row_count > 1 and len(unique_value_sets[column]) == 1 and unique_value_sets[column] and next(iter(unique_value_sets[column])):
            findings.append({
                "type": "constant_column",
                "severity": "warning",
                "column": column,
                "message": "Column has a single constant value across the dataset.",
                "value": 1.0,
            })

        if row_count > 20 and inferred_types.get(column) == "categorical" and len(unique_value_sets[column]) / row_count > 0.9:
            findings.append({
                "type": "high_cardinality",
                "severity": "warning",
                "column": column,
                "message": "Column has very high cardinality and may be a natural identifier or unstable grouping key.",
                "value": round((len(unique_value_sets[column]) / row_count) * 100, 2),
            })

        if row_count > 1 and inferred_types.get(column) == "categorical" and len(unique_value_sets[column]) == row_count:
            findings.append({
                "type": "possible_identifier",
                "severity": "info",
                "column": column,
                "message": "Column appears to act as a unique identifier because every row has a distinct value.",
                "value": round((len(unique_value_sets[column]) / row_count) * 100, 2),
            })

    if duplicate_row_count > 0:
        findings.append({
            "type": "duplicate_rows",
            "severity": "warning",
            "column": None,
            "message": f"Dataset contains {duplicate_row_count} duplicate rows.",
            "value": duplicate_percentage,
        })

    if malformed_rows > 0:
        findings.append({
            "type": "malformed_rows",
            "severity": "error",
            "column": None,
            "message": f"CSV contains {malformed_rows} inconsistent row(s).",
            "value": malformed_rows,
        })

    penalty = sum(missing_percentages.values()) * 0.35
    penalty += duplicate_percentage * 0.6
    penalty += malformed_rows * 5
    quality_score = int(max(0, min(100, round(100 - penalty))))

    if quality_score >= 90 and malformed_rows == 0:
        quality_status = "ready"
    elif quality_score >= 60 and malformed_rows == 0:
        quality_status = "ready_with_warnings"
    else:
        quality_status = "failed"

    return {
        "row_count": row_count,
        "column_count": column_count,
        "columns": columns,
        "missing_values": missing_values,
        "missing_percentages": missing_percentages,
        "duplicate_rows": duplicate_row_count,
        "duplicate_percentage": duplicate_percentage,
        "unique_value_counts": unique_value_counts,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "inferred_types": inferred_types,
        "quality_score": quality_score,
        "quality_status": quality_status,
        "status": quality_status,
        "findings": findings,
    }
