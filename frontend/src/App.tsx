import { useCallback, useEffect, useState } from "react";
import { clearAccessCode, setAccessCode } from "./api";
import { Home } from "./Home";
import { ProjectPage } from "./ProjectPage";

type Route = { name: "home" } | { name: "project"; projectId: string };

function currentRoute(): Route {
  const match = window.location.pathname.match(/^\/projects\/([0-9a-f-]+)\/?$/i);
  return match ? { name: "project", projectId: match[1] } : { name: "home" };
}

export default function App() {
  const [route, setRoute] = useState<Route>(currentRoute);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const handleHistory = () => setRoute(currentRoute());
    window.addEventListener("popstate", handleHistory);
    return () => window.removeEventListener("popstate", handleHistory);
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  function openProject(projectId: string, code: string) {
    setAccessCode(code);
    window.history.pushState({}, "", `/projects/${projectId}`);
    setRoute({ name: "project", projectId });
  }

  const closeProject = useCallback((message = "") => {
    clearAccessCode();
    window.history.pushState({}, "", "/");
    setRoute({ name: "home" });
    setNotice(message);
  }, []);

  return (
    <div className="app-shell">
      {route.name === "home" ? (
        <Home onOpen={openProject} />
      ) : (
        <ProjectPage projectId={route.projectId} onExit={closeProject} />
      )}
      {notice && (
        <div className="toast" role="status">
          {notice}
        </div>
      )}
    </div>
  );
}
