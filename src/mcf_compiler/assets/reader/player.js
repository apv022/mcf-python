"use strict";
(() => {
  // src/reader/essays.ts
  function countWords(response) {
    const value = response.trim();
    return value ? value.split(/\s+/u).length : 0;
  }
  function countSentences(response) {
    const value = response.trim();
    if (!value) return 0;
    const terminal = value.match(/[^.!?]+[.!?]+/gu)?.filter((part) => part.trim()).length ?? 0;
    const remainder = value.replace(/[^.!?]+[.!?]+/gu, "").trim();
    return terminal + (remainder ? 1 : 0);
  }
  function normalized(value) {
    return value.toLocaleLowerCase().replace(/\s+/gu, " ").trim();
  }
  function keywordMatches(response, keywords) {
    const value = normalized(response);
    return new Set(
      keywords.filter((keyword) => {
        const needle = normalized(keyword);
        if (!needle) return false;
        if (/^[\p{L}\p{N}_-]+$/u.test(needle))
          return new RegExp(
            `(^|[^\\p{L}\\p{N}_-])${needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}($|[^\\p{L}\\p{N}_-])`,
            "u"
          ).test(value);
        return value.includes(needle);
      })
    ).size;
  }
  function evaluateEssay(response, question) {
    const words = countWords(response), sentences = countSentences(response), matches = keywordMatches(response, question.keywords ?? []), feedback = [];
    if (question.minimum_sentences && sentences < question.minimum_sentences)
      feedback.push(`Write at least ${question.minimum_sentences} sentences. Current: ${sentences}.`);
    if (question.minimum_words && words < question.minimum_words)
      feedback.push(`Write at least ${question.minimum_words} words. Current: ${words}.`);
    const requiredKeywords = question.keywords?.length ? question.minimum_keywords ?? question.keywords.length : 0;
    if (matches < requiredKeywords)
      feedback.push(`Mention at least ${requiredKeywords} required concepts. Current: ${matches}.`);
    if (!question.minimum_words && !question.minimum_sentences && !requiredKeywords && !response.trim())
      feedback.push("Write a response before continuing.");
    return { complete: feedback.length === 0, words, sentences, keywords: matches, feedback };
  }

  // src/reader/storage.ts
  function storageKey(course2) {
    return `mcf:${course2.id}:${course2.version || "unversioned"}`;
  }
  function emptyState(course2) {
    return {
      schema: 1,
      courseId: course2.id,
      version: course2.version ?? null,
      questions: {},
      activities: {},
      assessments: {},
      lessons: {},
      questionOrders: {},
      completedAt: null
    };
  }
  function record(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }
  function validState(value, course2) {
    if (!record(value) || value.schema !== 1 || value.courseId !== course2.id || value.version !== (course2.version ?? null))
      return false;
    if (!["questions", "activities", "assessments", "lessons", "questionOrders"].every(
      (key2) => record(value[key2])
    ))
      return false;
    if (value.completedAt !== null && typeof value.completedAt !== "string") return false;
    const booleans = (item) => record(item) && Object.values(item).every((entry) => typeof entry === "boolean");
    if (!booleans(value.activities) || !booleans(value.lessons)) return false;
    if (!Object.values(value.questionOrders).every(
      (entry) => Array.isArray(entry) && entry.every((id) => typeof id === "string")
    ))
      return false;
    if (!Object.values(value.questions).every(
      (entry) => record(entry) && typeof entry.complete === "boolean" && (typeof entry.correct === "boolean" || entry.correct === null)
    ))
      return false;
    return Object.values(value.assessments).every(
      (entry) => record(entry) && typeof entry.submitted === "boolean" && typeof entry.score === "number" && Number.isFinite(entry.score) && typeof entry.possible === "number" && Number.isFinite(entry.possible) && (typeof entry.passed === "boolean" || entry.passed === null)
    );
  }
  function loadState(course2) {
    try {
      const value = JSON.parse(localStorage.getItem(storageKey(course2)) || "null");
      return validState(value, course2) ? value : emptyState(course2);
    } catch {
      return emptyState(course2);
    }
  }
  function saveState(course2, state2) {
    try {
      localStorage.setItem(storageKey(course2), JSON.stringify(state2));
    } catch {
    }
  }

  // src/reader/import-export.ts
  function wireTransfer(course2, getState) {
    document.querySelector("[data-export]")?.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(getState(), null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${course2.id}-progress.json`;
      link.click();
      URL.revokeObjectURL(link.href);
    });
    document.querySelector("[data-import]")?.addEventListener("change", async (event) => {
      try {
        const file = event.target.files?.[0];
        if (!file) return;
        const value = JSON.parse(await file.text());
        if (!validState(value, course2)) throw new Error();
        saveState(course2, value);
        location.reload();
      } catch {
        alert("This is not a valid progress file for this course version.");
      }
    });
  }

  // src/reader/questions.ts
  function hasResponse(value) {
    return Array.isArray(value) ? value.length > 0 : String(value ?? "").trim().length > 0;
  }
  function evaluateQuestion(question, response) {
    switch (question.type) {
      case "multiple_select":
        return JSON.stringify([...response].sort()) === JSON.stringify([...question.answer].sort());
      case "true_false":
        return response === "true" === question.answer;
      case "numeric":
        return hasResponse(response) && Number.isFinite(Number(response)) && Math.abs(Number(response) - Number(question.answer)) <= (question.tolerance ?? 0);
      case "short_answer":
        return String(response).trim().toLocaleLowerCase() === String(question.answer).trim().toLocaleLowerCase();
      case "essay":
        return null;
      default:
        return response === question.answer;
    }
  }
  function responseFrom(element) {
    const inputs = [
      ...element.querySelectorAll("input,textarea")
    ];
    if (element.dataset.type === "multiple_select")
      return inputs.filter((input) => input instanceof HTMLInputElement && input.checked).map((input) => input.value);
    const checked = inputs.find((input) => input instanceof HTMLInputElement && input.checked);
    return checked?.value ?? inputs[0]?.value ?? "";
  }
  function completion(question, response, requireCorrect) {
    if (question.type === "essay") {
      const result = evaluateEssay(String(response ?? ""), question);
      return { complete: result.complete, correct: null, feedback: result.feedback };
    }
    if (!hasResponse(response))
      return { complete: false, correct: null, feedback: ["Add a response first."] };
    const correct = evaluateQuestion(question, response);
    return { complete: requireCorrect ? correct === true : true, correct, feedback: [] };
  }

  // src/reader/progress.ts
  function percent(course2, state2) {
    return course2.lessons.length ? Math.round(
      course2.lessons.filter((lesson2) => state2.lessons[lesson2.id]).length / course2.lessons.length * 100
    ) : 0;
  }
  function refreshProgress(course2, state2) {
    const value = percent(course2, state2);
    document.querySelectorAll("[data-progress]").forEach((node) => {
      node.textContent = `${value}%`;
    });
    document.querySelectorAll("[data-progress-bar]").forEach((node) => {
      node.style.width = `${value}%`;
    });
    document.querySelectorAll("[data-lesson-id]").forEach((node) => node.classList.toggle("done", !!state2.lessons[node.dataset.lessonId ?? ""]));
    if (value === 100) {
      state2.completedAt || (state2.completedAt = (/* @__PURE__ */ new Date()).toISOString());
      document.querySelectorAll(".badge").forEach((node) => node.classList.remove("hidden"));
      document.querySelectorAll("[data-completion-date]").forEach((node) => {
        node.textContent = new Date(state2.completedAt).toLocaleDateString();
      });
    }
  }

  // src/reader/player.ts
  var course = window.MCF_COURSE;
  if (location.protocol === "file:") document.documentElement.classList.add("file-protocol");
  var state = loadState(course);
  var lessonId = document.body.dataset.lesson;
  var standalone = document.body.dataset.standalone === "true";
  var activeLessonId = lessonId || course.lessons[0]?.id;
  var lesson = course.lessons.find((item) => item.id === activeLessonId);
  var activeSection = () => standalone ? document.querySelector(`.standalone-lesson[data-lesson="${CSS.escape(activeLessonId || "")}"]`) : document;
  if (standalone) {
    const requested = decodeURIComponent(location.hash.replace(/^#lesson-/, ""));
    if (course.lessons.some((item) => item.id === requested)) activeLessonId = requested;
    lesson = course.lessons.find((item) => item.id === activeLessonId);
    document.querySelectorAll(".standalone-lesson").forEach((section) => {
      section.classList.toggle("active", section.dataset.lesson === activeLessonId);
    });
    document.querySelectorAll(".lesson-link").forEach(
      (link) => link.addEventListener("click", () => {
        activeLessonId = link.dataset.lessonId || activeLessonId;
        lesson = course.lessons.find((item) => item.id === activeLessonId);
        document.querySelectorAll(".standalone-lesson").forEach(
          (section) => section.classList.toggle("active", section.dataset.lesson === activeLessonId)
        );
      })
    );
    window.addEventListener("hashchange", () => {
      const next = decodeURIComponent(location.hash.replace(/^#lesson-/, ""));
      if (!course.lessons.some((item) => item.id === next)) return;
      activeLessonId = next;
      lesson = course.lessons.find((item) => item.id === activeLessonId);
      document.querySelectorAll(".standalone-lesson").forEach(
        (section) => section.classList.toggle("active", section.dataset.lesson === activeLessonId)
      );
    });
  }
  var key = (activity, question) => `${activeLessonId}:${activity.id}${question ? `:${question.id}` : ""}`;
  function persist() {
    saveState(course, state);
    updateCompletion();
  }
  function restore(element, value) {
    if (value === void 0) return;
    element.querySelectorAll("input").forEach((input) => {
      input.checked = Array.isArray(value) ? value.includes(input.value) : input.value === String(value);
    });
    const text = element.querySelector(
      "textarea,input.text-response"
    );
    if (text) text.value = String(value);
  }
  function chooseQuestions(activity) {
    const activityKey = key(activity);
    if (state.questionOrders[activityKey]) return state.questionOrders[activityKey];
    const ids = activity.questions.map((question) => question.id);
    if (activity.randomize)
      for (let index = ids.length - 1; index > 0; index--) {
        const other = Math.floor(Math.random() * (index + 1));
        [ids[index], ids[other]] = [ids[other], ids[index]];
      }
    state.questionOrders[activityKey] = ids.slice(0, activity.question_pool_size ?? ids.length);
    saveState(course, state);
    return state.questionOrders[activityKey];
  }
  var selectedQuestions = (activity) => {
    const ids = new Set(chooseQuestions(activity));
    return activity.questions.filter((question) => ids.has(question.id));
  };
  function showFeedback(element, messages, result) {
    const output = element.querySelector(".feedback");
    output.textContent = messages.join(" ");
    output.className = `feedback ${result === true ? "correct" : result === false ? "incorrect" : ""}`;
  }
  function wireQuestion(activity, element) {
    const question = activity.questions.find((item) => item.id === element.dataset.id);
    const stateKey = key(activity, question);
    restore(element, state.questions[stateKey]?.response);
    element.querySelector(".hint-button")?.addEventListener("click", () => element.querySelector(".hint")?.classList.toggle("hidden"));
    element.querySelectorAll("input,textarea").forEach(
      (control) => control.addEventListener("input", () => {
        const response = responseFrom(element), previous = state.questions[stateKey];
        state.questions[stateKey] = {
          response,
          complete: previous?.complete ?? false,
          correct: previous?.correct ?? null
        };
        if (question.type === "essay") {
          const result = evaluateEssay(String(response), question);
          showFeedback(
            element,
            result.feedback.length ? result.feedback : ["Response saved. Completion requirements met."],
            null
          );
          if (activity.type === "assessment") state.questions[stateKey].complete = result.complete;
        }
        persist();
      })
    );
    if (activity.type !== "assessment")
      element.querySelector(".check-button")?.addEventListener("click", () => {
        const response = responseFrom(element), result = completion(question, response, activity.type === "practice");
        state.questions[stateKey] = { response, complete: result.complete, correct: result.correct };
        if (question.type === "essay")
          showFeedback(
            element,
            result.feedback.length ? result.feedback : ["Response saved. Completion requirements met."],
            null
          );
        else if (!hasResponse(response)) showFeedback(element, result.feedback, null);
        else
          showFeedback(
            element,
            [result.correct ? "Correct \u2014 nicely done." : "Not quite. Try again."],
            result.correct
          );
        if (result.correct === true)
          element.querySelector(".explanation")?.classList.remove("hidden");
        persist();
      });
  }
  function submitAssessment(activity, container) {
    const selected = selectedQuestions(activity), unmet = selected.filter((question) => {
      if (!question.required) return false;
      const response = state.questions[key(activity, question)]?.response;
      return question.type === "essay" ? !evaluateEssay(String(response ?? ""), question).complete : !hasResponse(response);
    });
    if (unmet.length) {
      container.querySelector(".assessment-result").textContent = `Complete all required questions before submitting: ${unmet.map((question) => question.id).join(", ")}.`;
      return;
    }
    let earned = 0, possible = 0;
    for (const question of selected) {
      const itemKey = key(activity, question), response = state.questions[itemKey]?.response;
      if (question.type === "essay") {
        const essay = evaluateEssay(String(response ?? ""), question);
        state.questions[itemKey] = { response, complete: essay.complete, correct: null };
      } else {
        const correct = evaluateQuestion(question, response);
        if (question.required || hasResponse(response)) {
          possible += question.points;
          if (correct) earned += question.points;
        }
        state.questions[itemKey] = { response, complete: hasResponse(response), correct };
      }
      container.querySelector(`[data-id="${CSS.escape(question.id)}"] .explanation`)?.classList.remove("hidden");
    }
    const score = possible ? earned / possible : 1, passed = activity.passing_score === void 0 ? null : score >= activity.passing_score;
    state.assessments[key(activity)] = { submitted: true, score, possible, passed };
    container.querySelector(".assessment-result").textContent = `Submitted score: ${earned}/${possible} (${Math.round(score * 100)}%). ${passed === null ? "Submission complete." : passed ? "Passed." : "Not passed."} Essays are completion-checked but excluded from automatic scoring.`;
    persist();
  }
  function updateCompletion() {
    if (lesson && activeLessonId) {
      for (const activity of lesson.activities ?? []) {
        const selected = selectedQuestions(activity);
        const complete = activity.type === "notes" ? !!state.activities[key(activity)] : activity.type === "assessment" ? !!state.assessments[key(activity)]?.submitted : selected.filter((question) => question.required).every((question) => state.questions[key(activity, question)]?.complete);
        state.activities[key(activity)] = complete;
        document.querySelector(`[data-activity="${CSS.escape(activity.id)}"]`)?.classList.toggle("complete", complete);
      }
      state.lessons[activeLessonId] = (lesson.activities ?? []).every(
        (activity) => state.activities[key(activity)]
      );
    }
    refreshProgress(course, state);
    saveState(course, state);
  }
  for (const activityElement of (activeSection() ?? document).querySelectorAll(".activity")) {
    const activity = lesson?.activities?.find((item) => item.id === activityElement.dataset.activity);
    if (!activity) continue;
    const order = chooseQuestions(activity), questions = activityElement.querySelector(".questions");
    for (const id of order) {
      const element = activityElement.querySelector(
        `.question[data-id="${CSS.escape(id)}"]`
      );
      if (element) {
        questions?.append(element);
        wireQuestion(activity, element);
      }
    }
    activityElement.querySelectorAll(".question").forEach((element) => {
      if (!order.includes(element.dataset.id)) element.remove();
    });
    activityElement.querySelector(".notes-complete")?.addEventListener("click", () => {
      state.activities[key(activity)] = true;
      persist();
    });
    activityElement.querySelector(".assessment-submit")?.addEventListener("click", () => submitAssessment(activity, activityElement));
    const submitted = state.assessments[key(activity)];
    if (submitted)
      activityElement.querySelector(".assessment-result").textContent = `Previously submitted: ${Math.round(submitted.score * 100)}%. ${submitted.passed === null ? "" : submitted.passed ? "Passed." : "Not passed."}`;
  }
  wireTransfer(course, () => state);
  updateCompletion();
})();
