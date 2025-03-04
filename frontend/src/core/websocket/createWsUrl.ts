/* Copyright 2024 Marimo. All rights reserved. */
import { Strings } from "@/utils/strings";
import { KnownQueryParams } from "../constants";

export function createWsUrl(sessionId: string): string {
  const searchParams = new URLSearchParams(window.location.search);
  searchParams.set(KnownQueryParams.sessionId, sessionId);
  return resolveToWsUrl(`ws?${searchParams.toString()}`);
}

export function resolveToWsUrl(relativeUrl: string): string {
  if (relativeUrl.startsWith("ws:") || relativeUrl.startsWith("wss:")) {
    return relativeUrl;
  }

  let baseUri = new URL(document.baseURI);

  if (document.baseURI.includes("localhost")) {
    baseUri = new URL("http://localhost:2718/");
  }

  const protocol = baseUri.protocol === "https:" ? "wss:" : "ws:";
  const host = baseUri.host;
  const pathname = baseUri.pathname;

  return `${protocol}//${host}${Strings.withoutTrailingSlash(pathname)}/${Strings.withoutLeadingSlash(relativeUrl)}`;
}
