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

    is_valid = verification.get("valid")

    if is_valid is None:
        is_valid = verification.get("overall_validity")

    if is_valid is None:
        is_valid = verification.get("overall")

    if is_valid is None:
        verification_list = verification.get("verification")

        if isinstance(verification_list, list):

            is_valid = (
                len(verification_list) > 0
                and all(
                    item.get("valid") is True
                    for item in verification_list
                    if isinstance(item, dict)
                )
                and all(
                    isinstance(item, dict)
                    and item.get("valid") is True
                    for item in verification_list
                )
            )

    if is_valid is not True:

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

    USER REQUEST:
    {message}

    TASK:
    Generate EXACTLY {question_count} multiple-choice questions
    about the user's requested topic.

    OUTPUT REQUIREMENTS:
    - Return EXACTLY {question_count} questions.
    - Every question must have exactly 4 options.
    - Every question must have exactly ONE correct option.
    - The answer field must be a zero-based index: 0, 1, 2, or 3.
    - The explanation must explain why that exact option is correct.
    - Return ONLY valid JSON.
    - Do NOT return markdown.
    - Do NOT return ```json.
    - Do NOT add text outside JSON.

    REQUIRED JSON:

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
                "explanation": "Why the selected option is correct."
            }}
        ]
    }}

    STRICT ACCURACY RULES:

    1. Every question must have one and only one objectively correct answer.

    2. Before creating a question, independently determine the correct answer.

    3. Then create three clearly incorrect but plausible distractors.

    4. NEVER create an ambiguous question.

    5. NEVER create a question where the answer depends on interpretation.

    6. NEVER create a question where two options can reasonably be correct.

    7. NEVER create an option that is partially correct when the question asks for one exact answer.

    8. The correct answer MUST appear exactly once in the options.

    9. The answer index MUST point to that exact option.

    10. The explanation MUST match the selected option exactly.

    PROGRAMMING QUESTIONS:

    If the topic is Python or another programming language:

    - Verify the syntax before generating the question.
    - Verify the actual runtime behavior before selecting the answer.
    - Do not invent syntax.
    - Do not use ambiguous wording.
    - Prefer simple, well-established Python facts.
    - Avoid questions involving multiple interpretations.
    - Avoid obscure edge cases.
    - Avoid questions where different Python versions could behave differently.
    - Avoid questions involving implementation details unless absolutely certain.

    PYTHON SAFETY RULES:

    Do NOT create ambiguous questions about `del`.

    Do NOT ask vague questions such as:
    "What does del do?"
    
    Instead, if using `del`, specify the exact code, for example:
    `numbers = [10, 20, 30]`
    `del numbers[1]`
    and ask what the resulting list is.

    Do NOT create ambiguous questions about function default arguments.

    Do NOT use syntactically questionable options such as:
    `def func(a, b=)`
    
    Every code option must be valid Python syntax if it is presented as valid syntax.

    Do NOT use trailing commas, optional syntax, or unusual syntax merely to create distractors.

    Prefer straightforward questions such as:
    - What is the output of a simple Python expression?
    - Which keyword defines a function?
    - Which data type stores key-value pairs?
    - Which method converts a string to uppercase?
    - What does len() return?
    - Which symbol starts a comment?
    - Which collection does not allow duplicate elements?
    - What is the result of a simple list operation?

    CODE VERIFICATION:

    For every programming question, mentally execute or parse the code
    before selecting the answer.

    For example, if the question contains:

    numbers = [10, 20, 30]
    print(numbers[1])

    the correct answer must be based on the actual Python result.

    Do not guess.

    OPTION RULES:

    All four options must be different.

    Do NOT use:
    - duplicate options
    - capitalization-only differences
    - punctuation-only differences
    - whitespace-only differences
    - synonyms representing the same answer
    - two options that are both technically correct
    - an option that contains the correct answer plus extra misleading text

    QUESTION QUALITY:

    Questions must be:
    - clear
    - concise
    - educational
    - directly related to the requested topic
    - objectively answerable

    Avoid:
    - vague wording
    - trick questions
    - subjective questions
    - controversial facts
    - uncertain facts
    - obscure implementation details
    - questions with multiple valid interpretations

    FINAL SELF-CHECK:

    Before returning the JSON, independently check EACH question:

    A. Is the question factually correct?
    B. Is there exactly one correct option?
    C. Is the correct answer actually present?
    D. Does the answer index point to the correct option?
    E. Is every option distinct?
    F. Does the explanation match the selected option?
    G. Is the question unambiguous?
    H. For programming questions, is the syntax and behavior correct?
    I. Is the required question count exactly {question_count}?
    J. Does every question contain exactly 4 options?

    If ANY question fails one of these checks, discard that question
    and create a new one.

    Return the JSON only after ALL questions pass these checks.
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