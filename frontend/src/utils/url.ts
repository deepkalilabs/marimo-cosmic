/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Resolve the path to a URL.
 *
 * If its a relative path, it will be resolved to the current origin.
 *
 * If document.baseURI is set, it will be used as the base URL.
 */
export function asURL(path: string): URL {
  console.log("🔍 document.baseURI", document.baseURI);
  if (document.baseURI.includes("localhost")) {
    return new URL(path, `http://localhost:2718`);
  }
  return new URL(path, document.baseURI);
}
