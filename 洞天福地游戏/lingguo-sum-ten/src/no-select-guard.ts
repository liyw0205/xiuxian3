const style = document.createElement("style");
style.textContent = [
  "*{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;}",
  "html,body{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;}",
  "img,svg,canvas{-webkit-user-drag:none;user-select:none;}",
  "input,textarea{-webkit-user-select:text;user-select:text;}",
  "button{-webkit-tap-highlight-color:transparent;}",
].join("");
document.head.appendChild(style);

const prevent = (event: Event) => {
  const target = event.target;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
  event.preventDefault();
};

document.addEventListener("selectstart", prevent);
document.addEventListener("contextmenu", prevent);
document.addEventListener("dragstart", prevent);
