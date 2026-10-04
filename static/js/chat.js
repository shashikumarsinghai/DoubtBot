const chat = document.getElementById("chat");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send-button");

let currentController = null;
let isTyping = false;

hljs.configure({
    languages: [
        "c",
        "cpp",
        "python",
        "javascript",
        "java",
        "html",
        "css",
        "sql",
        "bash"
    ]
});

function addCopyButtons(container) {

    container.querySelectorAll("pre").forEach(function (pre) {

        if (pre.querySelector(".copy-code-button")) {
            return;
        }

        const button = document.createElement("button");

        button.textContent = "Copy";
        button.classList.add("copy-code-button");

        button.addEventListener("click", async function () {

            const code = pre.querySelector("code");

            if (!code) {
                return;
            }

            try {

                await navigator.clipboard.writeText(
                    code.innerText
                );

                button.textContent = "Copied!";

                setTimeout(function () {
                    button.textContent = "Copy";
                }, 1500);

            } catch (error) {

                console.error(
                    "Copy code error:",
                    error
                );

            }

        });

        pre.appendChild(button);

    });

}

// --------------------------------------------------
// TYPING EFFECT
// --------------------------------------------------

function typeBotMessage(botMessage, text) {

    let index = 0;

    isTyping = true;
    sendButton.textContent = "⏹️ Stop";

    botMessage.innerHTML = "";

    const interval = setInterval(function () {

        if (!isTyping) {

            clearInterval(interval);

            botMessage.textContent =
                "Generation stopped.";

            sendButton.textContent = "Send";

            return;
        }

        if (index >= text.length) {

            clearInterval(interval);

            isTyping = false;

            botMessage.innerHTML =
                marked.parse(text);

            botMessage.querySelectorAll("pre code").forEach(function (block) {
                hljs.highlightElement(block);
            });

            addCopyButtons(botMessage);
            addRegenerateButton(botMessage);

            sendButton.textContent = "Send";

            chat.scrollTop =
                chat.scrollHeight;

            return;
        }

        index++;

        const currentText =
            text.substring(0, index);

        botMessage.innerHTML =
            marked.parse(currentText);

        chat.scrollTop =
            chat.scrollHeight;

    }, 15);
}

// --------------------------------------------------
// TYPING EFFECT
// --------------------------------------------------
function addRegenerateButton(botMessage) {

    if (botMessage.querySelector(".regenerate-button")) {
        return;
    }

    const button = document.createElement("button");

    button.textContent = "🔄 Regenerate";
    button.classList.add("regenerate-button");

    button.addEventListener("click", async function () {

        if (currentController || isTyping) {
            return;
        }

        button.disabled = true;
        button.textContent = "🔄 Regenerating...";

        try {

            currentController = new AbortController();

            const response = await fetch("/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    regenerate: true
                }),
                signal: currentController.signal
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "Regeneration failed"
                );
            }

            botMessage.innerHTML = "";

            button.remove();

            currentController = null;

            typeBotMessage(
                botMessage,
                data.reply
            );

        } catch (error) {

            if (error.name === "AbortError") {

                botMessage.textContent =
                    "Generation stopped.";

            } else {

                console.error(
                    "Regenerate error:",
                    error
                );

                botMessage.textContent =
                    "❌ Regeneration failed.";
            }

        } finally {

            currentController = null;

            button.disabled = false;

            if (!isTyping) {
                sendButton.textContent = "Send";
            }

        }

    });

    botMessage.appendChild(button);
}

async function sendMessage() {

    const message = messageInput.value.trim();

    if (currentController) {
        return;
    }

    if (isTyping) {
        return;
    }

    if (message === "") {
        return;
    }

    const userMessage = document.createElement("div");
    userMessage.classList.add("message", "user");
    userMessage.textContent = message;
    chat.appendChild(userMessage);

    messageInput.value = "";

    const botMessage = document.createElement("div");
    botMessage.classList.add("message", "bot");
    botMessage.textContent = "Thinking... 🤔";
    chat.appendChild(botMessage);

    chat.scrollTop = chat.scrollHeight;

    try {

        currentController = new AbortController();

        sendButton.textContent = "⏹️ Stop";

        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            }),
            signal: currentController.signal
        });

        const data = await response.json();

        // =========================
        // QUIZ RESPONSE
        // =========================

        if (data.type === "quiz") {

            botMessage.innerHTML = "";

            const quiz = data.quiz;

            const quizContainer = document.createElement("div");
            quizContainer.classList.add("quiz-container");

            const title = document.createElement("h2");
            title.textContent = "📝 " + quiz.title;

            quizContainer.appendChild(title);

            quiz.questions.forEach((question, index) => {

                const questionBox = document.createElement("div");
                questionBox.classList.add("quiz-question");

                const questionTitle = document.createElement("h3");

                questionTitle.textContent =
                    `${index + 1}. ${question.question}`;

                questionBox.appendChild(questionTitle);

                question.options.forEach((option, optionIndex) => {

                    const label = document.createElement("label");
                    label.classList.add("quiz-option");

                    const radio = document.createElement("input");

                    radio.type = "radio";
                    radio.name = `question-${index}`;
                    radio.value = optionIndex;

                    label.appendChild(radio);

                    const text = document.createTextNode(
                        " " + option
                    );

                    label.appendChild(text);

                    questionBox.appendChild(label);

                });

                quizContainer.appendChild(questionBox);

            });

            const submitButton = document.createElement("button");

            submitButton.textContent = "Submit Quiz";
            submitButton.classList.add("submit-quiz");

            submitButton.addEventListener("click", async function () {

                const answers = [];

                quiz.questions.forEach((question, index) => {

                    const selected = document.querySelector(
                        `input[name="question-${index}"]:checked`
                    );

                    if (selected) {
                        answers.push(parseInt(selected.value));
                    } else {
                        answers.push(-1);
                    }

                });

                try {

                    const resultResponse = await fetch(
                        "/submit-quiz",
                        {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                answers: answers
                            })
                        }
                    );

                    const result =
                        await resultResponse.json();

                    showQuizResult(
                        quizContainer,
                        result
                    );

                    submitButton.disabled = true;

                } catch (error) {

                    console.error(
                        "Quiz submit error:",
                        error
                    );

                }

            });

            quizContainer.appendChild(submitButton);

            botMessage.appendChild(quizContainer);

        } else {

            // Normal AI response
            typeBotMessage(
                botMessage,
                data.reply
            );

        }

    } catch (error) {

        if (error.name === "AbortError") {

            isTyping = false;

            botMessage.textContent =
                "Generation stopped.";

            return;
        }

        isTyping = false;

        botMessage.textContent =
            "Something went wrong. Please try again.";

        console.error(error);

    } finally {

        currentController = null;

        if (!isTyping) {
            sendButton.textContent = "Send";
        }

    }

    chat.scrollTop = chat.scrollHeight;
}


function showQuizResult(container, result) {

    const resultBox = document.createElement("div");

    resultBox.classList.add("quiz-result");

    resultBox.innerHTML = `
        <h2>🎉 Quiz Result</h2>
        <p>
            Your Score:
            <strong>${result.score}/${result.total}</strong>
        </p>
    `;

    result.results.forEach((item, index) => {

        const answerBox = document.createElement("div");

        answerBox.classList.add("quiz-answer");

        const correctOption =
            item.correct >= 0
                ? String.fromCharCode(65 + item.correct)
                : "";

        const selectedOption =
            item.selected >= 0
                ? String.fromCharCode(65 + item.selected)
                : "Not answered";

        answerBox.innerHTML = `
            <p><strong>${index + 1}. ${item.question}</strong></p>

            <p>Your answer:
                ${selectedOption}
            </p>

            <p>Correct answer:
                <strong>${correctOption}</strong>
            </p>

            <p>
                ${item.explanation}
            </p>
        `;

        resultBox.appendChild(answerBox);

    });

    container.appendChild(resultBox);
}


// --------------------------------------------------
// SEND / STOP BUTTON
// --------------------------------------------------

sendButton.addEventListener("click", function () {

    if (currentController) {

        currentController.abort();

        return;
    }

    if (isTyping) {

        isTyping = false;

        sendButton.textContent = "Send";

        return;
    }

    sendMessage();

});


messageInput.addEventListener("keydown", function (event) {

    if (event.key === "Enter") {

        if (currentController || isTyping) {
            return;
        }

        sendMessage();

    }

});


const clearButton =
    document.getElementById("clear-button");

clearButton.addEventListener(
    "click",
    async function () {

        try {

            const response =
                await fetch(
                    "/clear-chat",
                    {
                        method: "POST"
                    }
                );

            if (response.ok) {

                chat.innerHTML = `
                    <div class="message bot">
                        Hello! 👋 What would you like to learn today?
                    </div>
                `;

                window.location.href =
                    "/new-chat";

            }

        } catch (error) {

            console.error(
                "Clear chat error:",
                error
            );

        }

    }
);


// --------------------------------------------------
// PDF RAG
// --------------------------------------------------

const pdfFile =
    document.getElementById("pdf-file");

const uploadPdfButton =
    document.getElementById(
        "upload-pdf-button"
    );

const removePdfButton =
    document.getElementById(
        "remove-pdf-button"
    );

const pdfStatus =
    document.getElementById(
        "pdf-status"
    );


// --------------------------------------------------
// UPLOAD PDF
// --------------------------------------------------

uploadPdfButton.addEventListener(
    "click",
    async function () {

        const file =
            pdfFile.files[0];

        if (!file) {

            pdfStatus.textContent =
                "Please select a PDF.";

            return;
        }

        const formData =
            new FormData();

        formData.append(
            "pdf",
            file
        );

        pdfStatus.textContent =
            "Indexing PDF for RAG... ⏳";

        uploadPdfButton.disabled =
            true;

        try {

            const response =
                await fetch(
                    "/upload-pdf",
                    {
                        method: "POST",
                        body: formData
                    }
                );

            const data =
                await response.json();

            if (response.ok) {

                pdfStatus.textContent =
                    `✅ ${data.filename} | ` +
                    `${data.pages} pages | ` +
                    `${data.chunks} chunks`;

                removePdfButton.style.display =
                    "inline-block";

                pdfFile.value = "";

            } else {

                pdfStatus.textContent =
                    `❌ ${data.error}`;

            }

        } catch (error) {

            console.error(
                "PDF upload error:",
                error
            );

            pdfStatus.textContent =
                "❌ Upload failed.";

        } finally {

            uploadPdfButton.disabled =
                false;

        }

    }
);


// --------------------------------------------------
// REMOVE PDF
// --------------------------------------------------

removePdfButton.addEventListener(
    "click",
    async function () {

        removePdfButton.disabled =
            true;

        try {

            const response =
                await fetch(
                    "/remove-pdf",
                    {
                        method: "POST"
                    }
                );

            const data =
                await response.json();

            if (response.ok) {

                pdfStatus.textContent =
                    "PDF removed. You can upload another PDF.";

                removePdfButton.style.display =
                    "none";

                pdfFile.value = "";

            } else {

                pdfStatus.textContent =
                    `❌ ${data.error}`;

            }

        } catch (error) {

            console.error(
                "Remove PDF error:",
                error
            );

            pdfStatus.textContent =
                "❌ Could not remove PDF.";

        } finally {

            removePdfButton.disabled =
                false;

        }

    }
);


// --------------------------------------------------
// CHECK ACTIVE PDF ON PAGE LOAD
// --------------------------------------------------

async function checkPdfStatus() {

    try {

        const response =
            await fetch("/pdf-status");

        const data =
            await response.json();

        if (data.active) {

            pdfStatus.textContent =
                `📄 ${data.filename} | ${data.pages} pages`;

            removePdfButton.style.display =
                "inline-block";

        } else {

            removePdfButton.style.display =
                "none";

        }

    } catch (error) {

        console.error(
            "PDF status error:",
            error
        );

    }

}


checkPdfStatus();


const menuButton =
    document.getElementById(
        "menu-button"
    );

const dashboardMenu =
    document.getElementById(
        "dashboard-menu"
    );

menuButton.addEventListener(
    "click",
    function () {

        dashboardMenu.classList.toggle(
            "show"
        );

    }
);


const themeButton =
    document.getElementById(
        "theme-button"
    );

themeButton.addEventListener(
    "click",
    function () {

        document.body.classList.toggle(
            "dark-mode"
        );

        if (
            document.body.classList.contains(
                "dark-mode"
            )
        ) {

            themeButton.textContent =
                "☀️ Light Mode";

            localStorage.setItem(
                "theme",
                "dark"
            );

        } else {

            themeButton.textContent =
                "🌙 Dark Mode";

            localStorage.setItem(
                "theme",
                "light"
            );

        }

    }
);


if (
    localStorage.getItem("theme") ===
    "dark"
) {

    document.body.classList.add(
        "dark-mode"
    );

    themeButton.textContent =
        "☀️ Light Mode";

}


const closeMenuButton =
    document.getElementById(
        "close-menu-button"
    );

closeMenuButton.addEventListener(
    "click",
    function () {

        dashboardMenu.classList.remove(
            "show"
        );

    }
);


// --------------------------------------------------
// LOAD CONVERSATION
// --------------------------------------------------

async function loadConversation() {

    try {

        const response =
            await fetch(
                "/conversation-messages"
            );

        const data =
            await response.json();

        if (
            !data.messages ||
            data.messages.length === 0
        ) {

            return;

        }

        chat.innerHTML = "";

        data.messages.forEach(
            function (message) {

                const messageElement =
                    document.createElement(
                        "div"
                    );

                messageElement.classList.add(
                    "message",
                    message.role === "user"
                        ? "user"
                        : "bot"
                );

                if (
                    message.role ===
                    "user"
                ) {

                    messageElement.textContent =
                        message.content;

                } else {

                    messageElement.innerHTML =
                        marked.parse(
                            message.content
                        );

                    messageElement
                        .querySelectorAll(
                            "pre code"
                        )
                        .forEach(
                            function (block) {

                                hljs.highlightElement(
                                    block
                                );

                            }
                        );

                    addCopyButtons(
                        messageElement
                    );

                    addRegenerateButton(
                        messageElement
                    );

                }

                chat.appendChild(
                    messageElement
                );

            }
        );

        chat.scrollTop =
            chat.scrollHeight;

    } catch (error) {

        console.error(
            "Conversation loading error:",
            error
        );

    }

}

loadConversation();