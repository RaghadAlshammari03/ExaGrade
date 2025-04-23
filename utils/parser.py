def group_papers_by_id(exam):
    """
    Groups student papers by their manual_id (group_key).
    Returns a dict of {group_key: [papers]} and a flat list of unmatched keys.
    """
    from exams.models import StudentPaper

    grouped = {}
    unmatched = []

    papers = StudentPaper.objects.filter(exam=exam)

    for paper in papers:
        # If manual_id exists, use it
        if paper.manual_id:
            group_key = paper.manual_id.strip()
        else:
            # Fallback: unmatched_<paper.id>
            group_key = f"unmatched_{paper.id}"

        # Update paper group_key if not set or changed
        if paper.group_key != group_key:
            paper.group_key = group_key
            paper.needs_regrading = True  # New group, needs regrading
            paper.save()

        if group_key not in grouped:
            grouped[group_key] = []
        grouped[group_key].append(paper)

        if "unmatched_" in group_key:
            unmatched.append(group_key)

    return grouped, unmatched
