/* Copyright 2024 Marimo. All rights reserved. */
import { EditApp } from "@/core/edit-app";
import { AppChrome } from "../editor/chrome/wrapper/app-chrome";
import { CommandPalette } from "../editor/controls/command-palette";
import { KnownQueryParams } from "@/core/constants";
import type { UserConfig } from "@/core/config/config-schema";
import type { AppConfig } from "@/core/config/config-schema";
import { useEffect } from "react";

declare const posthog: any;

interface Props {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

const hideChrome = (() => {
  const url = new URL(window.location.href);
  return url.searchParams.get(KnownQueryParams.showChrome) === "false";
})();

const EditPage = (props: Props) => {
  useEffect(() => {
    posthog.capture("notebook_opened", {
      props: props.appConfig || "unknown",
    });
  }, [props.appConfig]);

  if (hideChrome) {
    return (
      <>
        <EditApp hideControls={true} {...props} />
        <CommandPalette />
      </>
    );
  }

  return (
    <AppChrome>
      <EditApp {...props} />
      <CommandPalette />
    </AppChrome>
  );
};

export default EditPage;
