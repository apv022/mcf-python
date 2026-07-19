"use strict";
(() => {
  // src/reader/library.ts
  var escape = (value) => String(value ?? "").replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]
  );
  var root = document.querySelector("#courses");
  if (root) {
    const courses = window.MCF_LIBRARY ?? [];
    root.innerHTML = courses.length ? courses.map((course) => {
      let state = {};
      try {
        state = JSON.parse(
          localStorage.getItem(`mcf:${course.id}:${course.version || "unversioned"}`) || "{}"
        );
      } catch {
      }
      const done = course.lessons.filter((id) => state.lessons?.[id]).length, progress = course.lessons.length ? Math.round(done / course.lessons.length * 100) : 0, cover = course.cover && /^https?:/i.test(course.cover) ? course.cover : course.cover ? `${course.id}/${course.cover}` : void 0;
      return `<a class="course-card" href="${encodeURIComponent(course.id)}/index.html">${cover ? `<img src="${encodeURI(cover)}" alt="">` : '<div class="cover-placeholder">MCF</div>'}<div class="course-card-content"><h2>${escape(course.title)}</h2><p>${escape(course.description)}</p><div class="course-card-status"><small>${escape((course.authors ?? []).join(", "))}</small><div class="progress"><i style="width:${progress}%"></i></div><b>${progress}%</b></div></div></a>`;
    }).join("") : '<div class="empty"><h2>No compiled courses yet</h2><p>Compile an MCF package to add it here.</p></div>';
  }
})();
