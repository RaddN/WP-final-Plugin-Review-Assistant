try:
    # Simulating the f-string issue with a single closing brace
    f"""
    details.category summary.cat-header:hover {{ background: #f0f0f1; }
    """
    print("F-string works!")
except ValueError as e:
    print(f"F-string failed as expected: {e}")
