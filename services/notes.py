# ======================== 
# NOTES
# ========================

def generate_notes(mistral_client, message):
    response = mistral_client.chat.complete(
        model="ministral-3b-2512",
        messages=[
            {
                "role": "system",
                "content": """
                You are a notes generator for DoubtBot.

                Create clear, structured study notes for the
                user's requested topic.

                Use Markdown formatting.

                Include:
                - Definition / introduction
                - Important concepts
                - Key points
                - Examples where useful
                - Short summary

                Keep the explanation student-friendly.
                """
            },
            {
                "role": "user",
                "content": message
            }
        ]
    )

    return (
        response
        .choices[0]
        .message
        .content
        .strip()
    )