(() => {
  "use strict";

  const data = window.PROJECT_DATA;
  const casesRoot = document.querySelector("#audio-cases");
  const audio = new Audio();
  let activeButton = null;

  const columns = [
    ["source", "Source"],
    ["reference", "Reference"],
    ["target", "Target"],
    ["head16", "RelFx Head@16"],
    ["random512", "Random@512"],
    ["cma512", "CMA-ES@512"]
  ];

  function audioPath(itemId, key) {
    return `assets/audio/${itemId}/${key}.flac`;
  }

  function metricLabel(example, key) {
    if (key === "reference") return "";
    return `L<sub>d</sub> ${example.ld[key].toFixed(3)}`;
  }

  function audioCell(example, key, label) {
    const source = audioPath(example.id, key);
    return `
      <td class="audio-cell">
        <button class="play-button" type="button" data-audio="${source}" aria-label="Play ${label} for ${example.title}" title="Play ${label}">
          <span aria-hidden="true">&#9654;</span>
        </button>
        <span class="cell-metric">${metricLabel(example, key)}</span>
      </td>`;
  }

  const header = columns.map(([, label]) => `<th scope="col">${label}</th>`).join("");
  const rows = data.cases.map((example, index) => {
    const topology = example.topology === "known" ? "Known" : "Hidden";
    const cells = columns.map(([key, label]) => audioCell(example, key, label)).join("");
    return `
      <tr>
        <th scope="row" class="example-cell">
          <a href="${example.sourceUrl}">${index + 1}. ${example.title}</a>
          <span>${topology}; ${example.genre}; ${example.chain.join(" &rarr; ")}</span>
          <small><a href="${example.licenseUrl}">${example.license}</a></small>
        </th>
        ${cells}
      </tr>`;
  }).join("");

  casesRoot.innerHTML = `
    <div class="audio-table-wrap">
      <table class="audio-table">
        <thead><tr><th scope="col">Example and target chain</th>${header}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  function resetButton(button) {
    if (!button) return;
    button.classList.remove("is-playing");
    button.querySelector("span").innerHTML = "&#9654;";
    button.title = button.title.replace("Pause", "Play");
  }

  function activateButton(button) {
    button.classList.add("is-playing");
    button.querySelector("span").innerHTML = "&#10074;&#10074;";
    button.title = button.title.replace("Play", "Pause");
  }

  document.querySelectorAll(".play-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const source = button.dataset.audio;
      if (activeButton === button && !audio.paused) {
        audio.pause();
        resetButton(button);
        return;
      }

      resetButton(activeButton);
      if (audio.src !== new URL(source, window.location.href).href) {
        audio.src = source;
      }
      activeButton = button;
      try {
        await audio.play();
        activateButton(button);
      } catch (error) {
        resetButton(button);
        activeButton = null;
      }
    });
  });

  audio.addEventListener("ended", () => {
    resetButton(activeButton);
    activeButton = null;
  });

  audio.addEventListener("pause", () => {
    if (!audio.ended) resetButton(activeButton);
  });
})();
