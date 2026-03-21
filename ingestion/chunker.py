from langchain_core.documents import Document


def chunk_problem(doc: dict) -> list[Document]:
    pid = str(doc["_id"])
    slug = doc.get("slug", "")
    difficulty = doc.get("difficulty", "")
    tags = ",".join(doc.get("tags", []))
    base_meta = {
        "problem_id": pid,
        "slug":       slug,
        "difficulty": difficulty,
        "tags":       tags,
    }
    chunks = []
    # Chunk 1: Problem Statement
    statement_parts = [doc.get("problem_statement", "")]
    constraints = doc.get("constraints", "")
    if constraints:
        statement_parts.append(f"Constraints: {constraints}")

    for ex in doc.get("examples", []):
        ex_text = f"Input: {ex.get('input', '')} Output: {ex.get('output', '')}"
        if ex.get("explanation"):
            ex_text += f" Explanation: {ex['explanation']}"
        statement_parts.append(ex_text)

    chunks.append(Document(
        page_content="\n".join(filter(None, statement_parts)),
        metadata={**base_meta, "chunk_type": "statement",
                  "hint_stage": 0, "doc_id": f"{pid}_statement"},
    ))

    #  Chunks 2–5: Individual Hint Stages
    hints = doc.get("hints", {})
    for stage_num, stage_key in enumerate(["stage_1", "stage_2", "stage_3", "stage_4"], start=1):
        hint_text = hints.get(
            stage_key) or f"No hint available for stage {stage_num}."
        chunks.append(Document(
            page_content=f"Hint stage {stage_num}: {hint_text}",
            metadata={**base_meta, "chunk_type": "hint",
                      "hint_stage": stage_num, "doc_id": f"{pid}_hint_{stage_num}"},
        ))

    #  Chunk 6: Editorial
    editorial = doc.get("editorial", {})
    editorial_text = editorial.get(
        "content", "") if isinstance(editorial, dict) else ""
    chunks.append(Document(
        page_content=editorial_text or "No editorial available.",
        metadata={**base_meta, "chunk_type": "editorial",
                  "hint_stage": 3, "doc_id": f"{pid}_editorial"},
    ))

    # Chunk 7: Solutions
    solutions = doc.get("solutions", {})
    solution_parts = []
    for lang in ["python", "java", "cpp"]:
        code = solutions.get(lang, "")
        if code:
            solution_parts.append(f"### {lang.upper()} solution:\n{code}")

    chunks.append(Document(
        page_content="\n\n".join(
            solution_parts) or "No solutions available yet.",
        metadata={**base_meta, "chunk_type": "solutions",
                  "hint_stage": 5, "doc_id": f"{pid}_solutions"},
    ))
    return chunks
