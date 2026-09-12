/* Show / hide password. The eye is how a person checks they typed it right. */
(function () {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".pw-eye");
    if (!btn) return;
    var input = document.getElementById(btn.getAttribute("data-pw"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
    btn.setAttribute("title", show ? "Hide password" : "Show password");
    var on = btn.querySelector(".eye-on");
    var off = btn.querySelector(".eye-off");
    if (on) on.hidden = show;
    if (off) off.hidden = !show;
  });
})();
