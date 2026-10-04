# =========================
# QUIZ
# =========================

import json
import re
import time

def verify_quiz(mistral_client, questions):

    verification_prompt = f"""
    You are a strict quiz accuracy verifier for DoubtBot.

    Verify every question in the quiz below.

    For EVERY question, check:

    1. The question is factually correct.
    2. The question has exactly one correct option.
    3. The provided answer index points to the actually correct option.
    4. The correct option directly answers the question.
    5. The explanation matches the correct option.
    6. The explanation does not contradict the question or options.
    7. For calculation questions, independently calculate the answer.
    8. For programming questions, independently verify the code behavior.
    9. Reject the question if the correct answer is uncertain.
    10. Reject the question if the question itself is invalid or ambiguous.

    Be strict.

    Do not assume that the generated answer is correct.

    Independently verify every answer.

    Return ONLY valid JSON in this format:

    {{
        "valid": true
    }}

    or:

    {{
        "valid": false
    }}

    Quiz:

    {json.dumps(questions, ensure_ascii=False)}
    """

    response = mistral_client.chat.complete(
        model="ministral-3b-2512",
        messages=[
            {
                "role": "system",
                "content": verification_prompt
            }
        ],
        response_format={
            "type": "json_object"
        }
    )

    content = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    if content.startswith("```"):
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

    verification = json.loads(content)

    if verification.get("valid") is not True:

        print("Quiz verification failed: ", verification)
        
        raise ValueError(
            "Quiz failed accuracy verification."
        )

    return True

def generate_quiz(mistral_client, message):

    match = re.search(
        r"\b(\d+)\s*(?:questions?|ques|quiz)\b",
        message,
        re.IGNORECASE
    )

    if match:
        question_count = int(match.group(1))
    else:
        question_count = 5

    question_count = max(1, min(question_count, 20))

    base_prompt = f"""
    You are a highly accurate quiz generator for DoubtBot.

    USER TOPIC:
    {message}

    YOUR TASK:

    Generate EXACTLY {question_count} multiple-choice questions
    about the user's requested topic.

    CRITICAL REQUIREMENTS:

    - Generate EXACTLY {question_count} questions.
    - Do NOT generate fewer.
    - Do NOT generate more.
    - Every question must have EXACTLY 4 options.
    - Every question must have EXACTLY ONE correct option.
    - Every question must be different.
    - Do NOT repeat questions.
    - Do NOT repeat options within the same question.
    - All 4 options must be different from each other.
    - The correct answer must be one of the 4 options.
    - The answer field must be a zero-based index.
    - The answer index must be 0, 1, 2, or 3.
    - The explanation must match the correct option.

    OPTION RULE:

    For every question, carefully compare all four options.

    Option A, B, C and D must represent different answers.

    Do NOT create options that are:
    - identical
    - duplicates with different capitalization
    - duplicates with extra spaces
    - duplicates with minor punctuation changes
    - essentially the same answer written differently

    Before returning the quiz, check every question individually
    and make sure all four options are unique.

    QUESTION RULE:

    Every question must have one clearly correct answer.

    Never create a question where:
    - two options could both be correct
    - no option is correct
    - the correct answer is missing
    - the answer index points to a wrong option

    QUALITY RULE:

    Questions must be clear, educational and directly related
    to the user's requested topic.

    Do not invent facts.

    For calculation questions:
    calculate the answer before selecting the answer index.

    For programming questions:
    independently verify the code behavior.

    EXPLANATION RULE:

    The explanation must briefly explain why the selected
    correct option is correct.

    Return ONLY valid JSON.

    Do NOT use markdown.
    Do NOT use ```json.
    Do NOT add text before or after the JSON.

    REQUIRED JSON STRUCTURE:

    {{
        "questions": [
            {{
                "question": "Question text",
                "options": [
                    "Option A",
                    "Option B",
                    "Option C",
                    "Option D"
                ],
                "answer": 0,
                "explanation": "Short explanation"
            }}
        ]
    }}

    FINAL CHECK BEFORE RETURNING JSON:

    Count the questions.

    Required number:
    {question_count}

    Count the options in every question.

    Required number:
    4

    Check that every question has:
    - a non-empty question
    - exactly 4 unique options
    - one correct option
    - a valid answer index
    - an explanation

    Return the JSON only after all checks pass.
    """

    previous_error = ""

    for attempt in range(3):

        try:

            retry_instruction = ""

            if previous_error:
                retry_instruction = f"""
                
                IMPORTANT RETRY INSTRUCTION:

                Your previous quiz failed validation.

                The exact validation error was:

                {previous_error}

                Fix this problem before generating the new quiz.

                Do not repeat the previous mistake.

                You MUST generate exactly {question_count} complete questions.
                """

            prompt = base_prompt + retry_instruction

            response = mistral_client.chat.complete(
                model="ministral-3b-2512",
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                response_format={
                    "type": "json_object"
                }
            )

            content = (
                response
                .choices[0]
                .message
                .content
                .strip()
            )

            if content.startswith("```"):
                content = content.replace("```json", "")
                content = content.replace("```", "")
                content = content.strip()

            quiz_data = json.loads(content)

            questions = quiz_data.get("questions", [])

            if len(questions) != question_count:
                raise ValueError(
                    f"Expected {question_count} questions, "
                    f"but received {len(questions)}."
                )

            validated_questions = []
            seen_questions = set()

            for question in questions:

                question_text = question.get(
                    "question",
                    ""
                ).strip()

                options = question.get(
                    "options",
                    []
                )

                answer = question.get(
                    "answer"
                )

                explanation = question.get(
                    "explanation",
                    ""
                ).strip()

                if not question_text:
                    raise ValueError(
                        "Quiz contains an empty question."
                    )

                if len(options) != 4:
                    raise ValueError(
                        "Every question must have exactly 4 options."
                    )

                if any(
                    not isinstance(option, str)
                    or not option.strip()
                    for option in options
                ):
                    raise ValueError(
                        "Every option must contain valid text."
                    )

                if answer not in [0, 1, 2, 3]:
                    raise ValueError(
                        "Quiz contains an invalid answer index."
                    )

                if not explanation:
                    raise ValueError(
                        "Quiz contains a question without an explanation."
                    )

                normalized_question = re.sub(
                    r"\s+",
                    " ",
                    question_text.lower()
                ).strip()

                if normalized_question in seen_questions:
                    raise ValueError(
                        "Quiz contains duplicate questions."
                    )

                seen_questions.add(
                    normalized_question
                )

                normalized_options = [
                    re.sub(
                        r"\s+",
                        " ",
                        option.strip().lower()
                    ).strip()
                    for option in options
                ]

                if len(set(normalized_options)) != 4:
                    raise ValueError(
                        "Quiz contains duplicate options."
                    )

                validated_questions.append({
                    "question": question_text,
                    "options": [
                        option.strip()
                        for option in options
                    ],
                    "answer": answer,
                    "explanation": explanation
                })

            quiz_data["questions"] = validated_questions

            verify_quiz(
                mistral_client,
                validated_questions
            )

            return quiz_data

        except json.JSONDecodeError as e:

            previous_error = f"Invalid JSON: {e}"

            print(
                f"Quiz JSON error. "
                f"Attempt {attempt + 1}/3: {e}"
            )

        except ValueError as e:

            previous_error = str(e)

            print(
                f"Quiz validation error. "
                f"Attempt {attempt + 1}/3: {e}"
            )

        except Exception as e:

            previous_error = str(e)

            print(
                f"Quiz generation error. "
                f"Attempt {attempt + 1}/3: {e}"
            )

        if attempt < 2:
            time.sleep(2)

    raise ValueError(
        "Unable to generate a valid quiz after 3 attempts."
    )