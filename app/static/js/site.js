// Runs on every page. It asks "Are you sure?" questions

function askBeforeSending(event) {
  const form = event.target;
  const question = form.getAttribute("data-confirm");
  if (!window.confirm(question)) {
    // Cancel was pressed: don't send the form
    event.preventDefault(); 
  }
}

// The forms only exist once the page has loaded
document.addEventListener("DOMContentLoaded", function () {
  for (const form of document.querySelectorAll("form[data-confirm]")) {
    form.addEventListener("submit", askBeforeSending);
  }
});
