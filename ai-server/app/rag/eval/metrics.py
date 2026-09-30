

def precision_at_k(relevant_flgs:list[bool],k:int)->float:
    top = relevant_flgs[:k]
    if not top:
        return 0.0

    return sum(top) / len(relevant_flgs)

def recall_at_k(evidence_found:list[bool])->float:
    if not evidence_found:
        return 0.0
    return sum(evidence_found) / len(evidence_found)


def mrr(evidence_flags:list[bool])->float:
    for i, rel in enumerate(evidence_flags):
        if rel:
            return 1.0 / (i+1)
    return 0.0


def spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end
