EXCELLENT_SCORE = 90
GOOD_SCORE = 80
AVERAGE_SCORE = 70
PASSING_SCORE = 60


def calculate_grade(score):
    """Tələbənin balına uyğun qiymət qaytarır."""
    if score >= EXCELLENT_SCORE:
        return "A"

    if score >= GOOD_SCORE:
        return "B"

    if score >= AVERAGE_SCORE:
        return "C"

    if score >= PASSING_SCORE:
        return "D"

    return "F"


def calculate_statistics(students):
    """Tələbə nəticələri əsasında statistikalar hesablayır."""
    if not students:
        return {
            "total_students": 0,
            "average_score": 0,
            "highest_score": 0,
            "lowest_score": 0
        }

    scores = [student["score"] for student in students]

    return {
        "total_students": len(students),
        "average_score": round(sum(scores) / len(scores), 1),
        "highest_score": max(scores),
        "lowest_score": min(scores)
    }