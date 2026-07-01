import { useEffect } from "react";
import GamePage from "@/pages/GamePage";

export default function App() {
  useEffect(() => {
    const preventSelection = (event: Event) => {
      const target = event.target;
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
      event.preventDefault();
    };

    document.addEventListener("selectstart", preventSelection);
    document.addEventListener("contextmenu", preventSelection);
    document.addEventListener("dragstart", preventSelection);

    return () => {
      document.removeEventListener("selectstart", preventSelection);
      document.removeEventListener("contextmenu", preventSelection);
      document.removeEventListener("dragstart", preventSelection);
    };
  }, []);

  return <GamePage />;
}
