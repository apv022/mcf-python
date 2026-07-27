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
    return `mcf:state-v2:${course2.id}:${course2.version || "unversioned"}`;
  }
  function emptyState(course2) {
    return {
      schema: 2,
      courseId: course2.id,
      version: course2.version ?? null,
      questions: {},
      activities: {},
      assessments: {},
      lessons: {},
      questionOrders: {},
      matchingOrders: {},
      orderingOrders: {},
      manualCompletions: {},
      completedAt: null
    };
  }
  function record(value) {
    return !!value && typeof value === "object" && !Array.isArray(value);
  }
  function validState(value, course2) {
    if (!record(value) || value.schema !== 2 || value.courseId !== course2.id || value.version !== (course2.version ?? null))
      return false;
    if (![
      "questions",
      "activities",
      "assessments",
      "lessons",
      "questionOrders",
      "matchingOrders",
      "orderingOrders",
      "manualCompletions"
    ].every((key2) => record(value[key2])))
      return false;
    if (value.completedAt !== null && typeof value.completedAt !== "string") return false;
    const booleans = (item) => record(item) && Object.values(item).every((entry) => typeof entry === "boolean");
    if (!booleans(value.activities) || !booleans(value.lessons) || !booleans(value.manualCompletions))
      return false;
    for (const map of [value.questionOrders, value.matchingOrders, value.orderingOrders])
      if (!Object.values(map).every(
        (entry) => Array.isArray(entry) && entry.every((id) => typeof id === "string")
      ))
        return false;
    if (!Object.values(value.questions).every(
      (entry) => record(entry) && typeof entry.complete === "boolean" && (typeof entry.correct === "boolean" || entry.correct === null) && typeof entry.attempted === "boolean" && typeof entry.checked === "boolean" && (typeof entry.earned === "number" || entry.earned === null)
    ))
      return false;
    return Object.values(value.assessments).every(
      (entry) => record(entry) && typeof entry.submitted === "boolean" && typeof entry.score === "number" && Number.isFinite(entry.score) && typeof entry.possible === "number" && Number.isFinite(entry.possible) && (typeof entry.passed === "boolean" || entry.passed === null) && typeof entry.pendingManual === "boolean"
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
  function numericResponse(value) {
    if (typeof value === "number") return Number.isFinite(value) ? value : void 0;
    if (typeof value !== "string" || !value.trim()) return;
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) return;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : void 0;
  }
  function responseComplete(question, value) {
    switch (question.type) {
      case "multiple_choice":
      case "true_false":
        return typeof value === "string" && value.length > 0;
      case "multiple_select":
        return Array.isArray(value) && value.length > 0 && value.every((id) => typeof id === "string") && new Set(value).size === value.length;
      case "numeric":
        return numericResponse(value) !== void 0;
      case "short_answer":
      case "essay":
      case "open_response":
        return typeof value === "string" && value.trim().length > 0;
      case "matching": {
        if (!value || typeof value !== "object" || Array.isArray(value)) return false;
        const actual = value;
        const ids = (question.premises ?? []).map((item) => item.id);
        const selected = ids.map((id) => actual[id]);
        return ids.length > 0 && selected.every((id) => typeof id === "string" && id.length > 0) && (question.reuse_responses || new Set(selected).size === selected.length);
      }
      case "ordering": {
        if (!Array.isArray(value)) return false;
        const expected = (question.items ?? []).map((item) => item.id);
        return value.length === expected.length && new Set(value).size === value.length && value.every((id) => typeof id === "string" && expected.includes(id));
      }
      default:
        return value !== null && value !== void 0 && String(value).trim().length > 0;
    }
  }
  function evaluateQuestion(question, response) {
    if (!responseComplete(question, response)) return false;
    switch (question.type) {
      case "multiple_select":
        return JSON.stringify([...response].sort()) === JSON.stringify([...question.answer].sort());
      case "true_false":
        return response === "true" === question.answer;
      case "numeric": {
        const tolerance = typeof question.tolerance === "number" ? { absolute: question.tolerance } : question.tolerance ?? { absolute: 0 };
        const parsed = numericResponse(response);
        const difference = Math.abs(parsed - Number(question.answer));
        return tolerance.absolute !== void 0 && difference <= tolerance.absolute || tolerance.relative !== void 0 && difference <= tolerance.relative * Math.abs(Number(question.answer));
      }
      case "short_answer":
        return (question.answers ?? [String(question.answer)]).some(
          (answer) => normalizeAnswer(String(response), question) === normalizeAnswer(answer, question)
        );
      case "essay":
      case "open_response":
        return null;
      case "matching": {
        const expected = question.answer;
        const actual = response;
        return Object.keys(expected).every((key2) => actual?.[key2] === expected[key2]);
      }
      case "ordering":
        return JSON.stringify(response) === JSON.stringify(question.answer);
      default:
        return response === question.answer;
    }
  }
  function normalizeAnswer(value, question) {
    const settings = question.normalization ?? {};
    if ((settings.unicode ?? "NFC") !== "none") value = value.normalize(settings.unicode ?? "NFC");
    if (settings.trim ?? true) value = value.trim();
    if (settings.collapse_whitespace) value = value.replace(/\s+/gu, " ");
    if (!(settings.case_sensitive ?? false)) value = value.toLocaleLowerCase();
    return value;
  }
  function earnedPoints(question, response) {
    if (!responseComplete(question, response)) return 0;
    if (question.type === "multiple_choice" && question.options?.some((option) => option.weight !== void 0))
      return (question.options.find((option) => option.id === response)?.weight ?? 0) * question.points;
    if (question.scoring === "partial" && question.type === "multiple_select") {
      const selected = new Set(response);
      const correct = new Set(question.answer);
      const incorrectTotal = (question.options?.length ?? 0) - correct.size;
      const correctSelected = [...selected].filter((id) => correct.has(id)).length;
      const incorrectSelected = [...selected].filter((id) => !correct.has(id)).length;
      return Math.max(
        0,
        correctSelected / correct.size - (incorrectTotal ? incorrectSelected / incorrectTotal : 0)
      ) * question.points;
    }
    if (question.scoring === "partial" && question.type === "matching") {
      const expected = question.answer;
      const actual = response;
      return Object.keys(expected).filter((key2) => actual?.[key2] === expected[key2]).length / Object.keys(expected).length * question.points;
    }
    if (question.scoring === "partial" && question.type === "ordering") {
      const expected = question.answer;
      const actual = response;
      return expected.filter((value, index) => actual?.[index] === value).length / expected.length * question.points;
    }
    return evaluateQuestion(question, response) ? question.points : 0;
  }
  function responseFrom(element) {
    if (element.dataset.type === "matching")
      return Object.fromEntries(
        [...element.querySelectorAll("select[data-premise]")].map((select) => [
          select.dataset.premise,
          select.value
        ])
      );
    if (element.dataset.type === "ordering")
      return [...element.querySelectorAll("[data-ordering-item]")].map(
        (item) => item.dataset.orderingItem
      );
    const inputs = [
      ...element.querySelectorAll("input,textarea")
    ];
    if (element.dataset.type === "multiple_select")
      return inputs.filter((input) => input instanceof HTMLInputElement && input.checked).map((input) => input.value);
    const checked = inputs.find((input) => input instanceof HTMLInputElement && input.checked);
    return checked?.value ?? inputs[0]?.value ?? "";
  }
  function completion(question, response, requireCorrect) {
    if (question.type === "essay" || question.type === "open_response") {
      const result = evaluateEssay(String(response ?? ""), question);
      return { complete: result.complete, correct: null, feedback: result.feedback };
    }
    if (!responseComplete(question, response))
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
    if (element.dataset.type === "matching" && value && typeof value === "object")
      element.querySelectorAll("select[data-premise]").forEach((select) => {
        select.value = String(value[select.dataset.premise] ?? "");
      });
    if (element.dataset.type === "ordering" && Array.isArray(value)) {
      const list = element.querySelector(".ordering-list");
      for (const id of value) {
        const item = element.querySelector(
          `[data-ordering-item="${CSS.escape(String(id))}"]`
        );
        if (item) list?.append(item);
      }
    }
  }
  function shuffled(ids, forbidden) {
    const result = [...ids];
    for (let index = result.length - 1; index > 0; index--) {
      const other = Math.floor(Math.random() * (index + 1));
      [result[index], result[other]] = [result[other], result[index]];
    }
    if (result.length > 1 && forbidden && result.every((value, index) => value === forbidden[index]))
      result.push(result.shift());
    return result;
  }
  function chooseQuestions(activity) {
    const activityKey = key(activity);
    if (state.questionOrders[activityKey]) return state.questionOrders[activityKey];
    const ids = activity.questions.map((question) => question.id);
    if (activity.randomize) ids.splice(0, ids.length, ...shuffled(ids));
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
  function showResponseFeedback(element, response) {
    const selected = new Set(Array.isArray(response) ? response : [String(response ?? "")]);
    element.querySelectorAll("[data-option-feedback]").forEach((node) => {
      node.classList.toggle("hidden", !selected.has(node.dataset.optionFeedback));
    });
  }
  function configureMatching(question, element, stateKey) {
    let order = state.matchingOrders[stateKey];
    const responseIds = (question.responses ?? []).map((item) => item.id);
    if (!order || order.length !== responseIds.length || order.some((id) => !responseIds.includes(id))) {
      const answer = question.answer;
      const answerOrder = answer ? (question.premises ?? []).map((premise) => answer[premise.id]) : void 0;
      order = shuffled(responseIds, answerOrder);
      state.matchingOrders[stateKey] = order;
    }
    const labels = new Map(
      [...element.querySelectorAll('option[value]:not([value=""])')].map(
        (option) => [option.value, option.textContent ?? option.value]
      )
    );
    element.querySelectorAll("select[data-premise]").forEach((select) => {
      const current = select.value;
      select.replaceChildren(new Option("Choose\u2026", ""));
      for (const id of order) select.add(new Option(labels.get(id) ?? id, id));
      select.value = current;
    });
    const enforceReuse = () => {
      if (question.reuse_responses) return;
      const controls = [...element.querySelectorAll("select[data-premise]")];
      const selected = new Set(controls.map((select) => select.value).filter(Boolean));
      for (const select of controls)
        for (const option of [...select.options])
          option.disabled = !!option.value && option.value !== select.value && selected.has(option.value);
    };
    element.querySelectorAll("select[data-premise]").forEach((select) => select.addEventListener("change", enforceReuse));
    enforceReuse();
  }
  function configureOrdering(question, element, stateKey) {
    const ids = (question.items ?? []).map((item) => item.id);
    let order = state.orderingOrders[stateKey];
    const answer = Array.isArray(question.answer) ? question.answer : void 0;
    if (!order || order.length !== ids.length || order.some((id) => !ids.includes(id))) {
      order = shuffled(ids, answer);
      state.orderingOrders[stateKey] = order;
    }
    restore(element, order);
    element.querySelectorAll("[data-move]").forEach(
      (button) => button.addEventListener("click", () => {
        const item = button.closest("[data-ordering-item]");
        const sibling = button.dataset.move === "up" ? item?.previousElementSibling : item?.nextElementSibling?.nextElementSibling;
        if (item && sibling) item.parentElement?.insertBefore(item, sibling);
        const response = responseFrom(element);
        state.orderingOrders[stateKey] = response;
        const previous = state.questions[stateKey];
        state.questions[stateKey] = questionState(response, previous, true);
        persist();
        item?.querySelector(`[data-move="${button.dataset.move}"]`)?.focus();
      })
    );
  }
  function questionState(response, previous, attempted = false) {
    return {
      response,
      complete: previous?.complete ?? false,
      correct: previous?.correct ?? null,
      attempted: previous?.attempted || attempted,
      checked: previous?.checked ?? false,
      earned: previous?.earned ?? null
    };
  }
  function wireQuestion(activity, element) {
    const question = activity.questions.find((item) => item.id === element.dataset.id);
    const stateKey = key(activity, question);
    restore(element, state.questions[stateKey]?.response);
    if (question.type === "matching") configureMatching(question, element, stateKey);
    if (question.type === "ordering") configureOrdering(question, element, stateKey);
    element.querySelector(".hint-button")?.addEventListener("click", () => element.querySelector(".hint")?.classList.toggle("hidden"));
    element.querySelectorAll("input,textarea,select").forEach(
      (control) => control.addEventListener("input", () => {
        const response = responseFrom(element), previous = state.questions[stateKey];
        state.questions[stateKey] = questionState(response, previous, true);
        if (question.type === "essay" || question.type === "open_response") {
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
        const response = responseFrom(element);
        const nonObjective = question.evaluation === "manual" || question.evaluation === "ungraded";
        const result = nonObjective ? {
          complete: responseComplete(question, response),
          correct: null,
          feedback: responseComplete(question, response) ? [
            question.evaluation === "manual" ? "Response submitted. Manual review is pending." : "Ungraded response saved."
          ] : ["Add a response first."]
        } : completion(
          question,
          response,
          activity.type === "practice" && question.evaluation !== "completion"
        );
        state.questions[stateKey] = {
          response,
          complete: result.complete,
          correct: result.correct,
          attempted: true,
          checked: true,
          earned: result.correct === null ? null : earnedPoints(question, response)
        };
        if (question.type === "essay" || question.type === "open_response")
          showFeedback(
            element,
            result.feedback.length ? result.feedback : ["Response saved. Completion requirements met."],
            null
          );
        else if (!responseComplete(question, response)) showFeedback(element, result.feedback, null);
        else if (nonObjective) showFeedback(element, result.feedback, null);
        else
          showFeedback(
            element,
            [result.correct ? "Correct \u2014 nicely done." : "Not quite. Try again."],
            result.correct
          );
        showResponseFeedback(element, response);
        element.querySelector(".explanation")?.classList.remove("hidden");
        persist();
      });
  }
  function submitAssessment(activity, container) {
    const selected = selectedQuestions(activity), unmet = selected.filter((question) => {
      if (!question.required) return false;
      const response = state.questions[key(activity, question)]?.response;
      return question.type === "essay" || question.type === "open_response" ? !evaluateEssay(String(response ?? ""), question).complete : !responseComplete(question, response);
    });
    if (unmet.length) {
      container.querySelector(".assessment-result").textContent = `Complete all required questions before submitting: ${unmet.map((question) => question.id).join(", ")}.`;
      return;
    }
    let earned = 0, possible = 0;
    for (const question of selected) {
      const itemKey = key(activity, question), response = state.questions[itemKey]?.response;
      if (question.evaluation === "manual" || question.evaluation === "ungraded") {
        state.questions[itemKey] = {
          response,
          complete: responseComplete(question, response),
          correct: null,
          attempted: true,
          checked: false,
          earned: null
        };
      } else if (question.type === "essay" || question.type === "open_response") {
        const essay = evaluateEssay(String(response ?? ""), question);
        state.questions[itemKey] = {
          response,
          complete: essay.complete,
          correct: null,
          attempted: true,
          checked: false,
          earned: null
        };
      } else {
        const correct = evaluateQuestion(question, response);
        if (question.points > 0 && (question.required || responseComplete(question, response))) {
          possible += question.points;
          earned += earnedPoints(question, response);
        }
        state.questions[itemKey] = {
          response,
          complete: responseComplete(question, response),
          correct,
          attempted: true,
          checked: true,
          earned: earnedPoints(question, response)
        };
      }
      container.querySelector(`[data-id="${CSS.escape(question.id)}"] .explanation`)?.classList.remove("hidden");
      showResponseFeedback(
        container.querySelector(`[data-id="${CSS.escape(question.id)}"]`),
        response
      );
    }
    const pendingManual = selected.some(
      (question) => (question.evaluation === "manual" || question.type === "essay") && question.required
    );
    const score = possible ? earned / possible : 0, passed = pendingManual || activity.passing_score === void 0 ? null : score >= activity.passing_score;
    state.assessments[key(activity)] = {
      submitted: true,
      score,
      possible,
      passed,
      pendingManual
    };
    container.querySelector(".assessment-result").textContent = `${pendingManual ? "Provisional automatic score" : "Submitted score"}: ${earned}/${possible} (${Math.round(score * 100)}%). ${pendingManual ? "Manual review pending." : passed === null ? "Submission complete." : passed ? "Passed." : "Not passed."}`;
    persist();
  }
  function findQuestion(id) {
    for (const activity of lesson?.activities ?? []) {
      const question = activity.questions.find((item) => item.id === id);
      if (question) return { activity, question };
    }
  }
  function conditionMet(condition) {
    const activity = condition.activity ? lesson?.activities?.find((item) => item.id === condition.activity) : condition.question ? findQuestion(condition.question)?.activity : void 0;
    const question = condition.question ? findQuestion(condition.question)?.question : void 0;
    if (!activity) return false;
    const activityKey = key(activity);
    const questionKey = question ? key(activity, question) : void 0;
    const questionStateValue = questionKey ? state.questions[questionKey] : void 0;
    const assessment = state.assessments[activityKey];
    switch (condition.requirement) {
      case "viewed":
        return !!document.querySelector(`[data-activity="${CSS.escape(activity.id)}"]`);
      case "attempted":
        return question ? !!questionStateValue?.attempted : activity.questions.some((item) => state.questions[key(activity, item)]?.attempted);
      case "answered":
        return question ? responseComplete(question, questionStateValue?.response) : activity.questions.filter((item) => item.required).every(
          (item) => responseComplete(item, state.questions[key(activity, item)]?.response)
        );
      case "submitted":
        return activity.type === "assignment" ? !!state.questions[`${activityKey}:submission`]?.complete : !!assessment?.submitted;
      case "passed":
        return assessment?.passed === true && (condition.minimum_score === void 0 || assessment.score >= condition.minimum_score);
      case "manually_marked_complete":
        return !!state.manualCompletions[questionKey ?? activityKey];
    }
  }
  function expressionMet(expression, depth = 1) {
    if (depth > 8) return false;
    const entries = expression.all ?? expression.any;
    if (!entries?.length) return false;
    const values = entries.map(
      (entry) => "requirement" in entry ? conditionMet(entry) : expressionMet(entry, depth + 1)
    );
    return expression.any ? values.some(Boolean) : values.every(Boolean);
  }
  function fallbackActivityComplete(activity) {
    const activityKey = key(activity);
    const required = selectedQuestions(activity).filter((question) => question.required);
    if (activity.type === "notes") return !!state.manualCompletions[activityKey];
    if (activity.type === "assessment") {
      const assessment = state.assessments[activityKey];
      return activity.passing_score === void 0 ? !!assessment?.submitted : assessment?.submitted === true && assessment.passed === true;
    }
    if (activity.type === "assignment")
      return !!state.questions[`${activityKey}:submission`]?.complete;
    if (activity.evaluation === "manual")
      return required.every((question) => state.questions[key(activity, question)]?.attempted);
    if (activity.evaluation === "completion")
      return required.every((question) => state.questions[key(activity, question)]?.complete);
    if (activity.evaluation === "ungraded")
      return !!state.manualCompletions[activityKey] || required.every(
        (question) => responseComplete(question, state.questions[key(activity, question)]?.response)
      );
    return required.every((question) => {
      const item = state.questions[key(activity, question)];
      return item?.checked && responseComplete(question, item.response);
    });
  }
  function wireAssignment(activity, element) {
    const stateKey = `${key(activity)}:submission`;
    const existing = state.questions[stateKey]?.response;
    const text = element.querySelector("[data-assignment-text]");
    const url = element.querySelector("[data-assignment-url]");
    if (text) text.value = existing?.text ?? "";
    if (url) url.value = existing?.url ?? "";
    element.querySelector(".assignment-submit")?.addEventListener("click", () => {
      const files = [
        ...element.querySelector("[data-assignment-files]")?.files ?? []
      ].map((file) => ({ name: file.name, size: file.size, type: file.type }));
      const response = { text: text?.value.trim(), url: url?.value.trim(), files };
      const modes = activity.submission?.modes ?? [];
      const validUrl = !response.url || (() => {
        try {
          return ["http:", "https:"].includes(new URL(response.url).protocol);
        } catch {
          return false;
        }
      })();
      const minimum = activity.submission?.minimum_files ?? 0;
      const maximum = activity.submission?.maximum_files ?? Infinity;
      const complete = validUrl && files.length >= minimum && files.length <= maximum && (modes.includes("text") && !!response.text || modes.includes("url") && !!response.url || modes.includes("file") && files.length > 0);
      state.questions[stateKey] = {
        response,
        complete,
        correct: null,
        attempted: true,
        checked: false,
        earned: null
      };
      element.querySelector(".assignment-result").textContent = complete ? "Submitted locally. Manual or host-platform review remains pending." : "Add a valid declared response and satisfy the file requirements before submitting.";
      persist();
    });
  }
  function updateCompletion() {
    if (lesson && activeLessonId) {
      for (const activity of lesson.activities ?? []) {
        const complete = fallbackActivityComplete(activity);
        state.activities[key(activity)] = complete;
        document.querySelector(`[data-activity="${CSS.escape(activity.id)}"]`)?.classList.toggle("complete", complete);
      }
      state.lessons[activeLessonId] = lesson.completion ? expressionMet(lesson.completion) : (lesson.activities ?? []).every((activity) => state.activities[key(activity)]);
    }
    refreshProgress(course, state);
    saveState(course, state);
  }
  function initializeActivities(scope, lessonId2) {
    const previousId = activeLessonId, previousLesson = lesson;
    activeLessonId = lessonId2;
    lesson = course.lessons.find((item) => item.id === lessonId2);
    if (!lesson) return;
    for (const activityElement of scope.querySelectorAll(".activity")) {
      const activity = lesson?.activities?.find(
        (item) => item.id === activityElement.dataset.activity
      );
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
        state.manualCompletions[key(activity)] = true;
        persist();
      });
      if (activity.type === "assignment") wireAssignment(activity, activityElement);
      activityElement.querySelector(".assessment-submit")?.addEventListener("click", () => submitAssessment(activity, activityElement));
      const submitted = state.assessments[key(activity)];
      if (submitted)
        activityElement.querySelector(".assessment-result").textContent = `Previously submitted: ${Math.round(submitted.score * 100)}%. ${submitted.passed === null ? "" : submitted.passed ? "Passed." : "Not passed."}`;
    }
    activeLessonId = previousId;
    lesson = previousLesson;
  }
  if (standalone)
    for (const section of document.querySelectorAll(".standalone-lesson")) {
      const id = section.dataset.lesson;
      if (id) initializeActivities(section, id);
    }
  else if (activeLessonId) initializeActivities(document, activeLessonId);
  wireTransfer(course, () => state);
  updateCompletion();
})();
