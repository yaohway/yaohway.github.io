// Evaluate on the wide-code fixture after setting a mobile viewport in Orca.
(() => {
  const root = document.documentElement;
  const body = document.body;
  const blocks = Array.from(document.querySelectorAll(".prose pre"), (pre) => {
    const original = pre.scrollLeft;
    pre.scrollLeft = 96;
    const moved = pre.scrollLeft;
    pre.scrollLeft = original;
    return {
      lexer: pre.querySelector("code").dataset.lang,
      client: pre.clientWidth,
      scroll: pre.scrollWidth,
      overflowX: getComputedStyle(pre).overflowX,
      moved
    };
  });
  const result = {
    viewport: [innerWidth, innerHeight],
    dpr: devicePixelRatio,
    coarsePointer: matchMedia("(pointer: coarse)").matches,
    document: [root.clientWidth, root.scrollWidth],
    body: [body.clientWidth, body.scrollWidth],
    documentScrollLeft: window.scrollX,
    blocks
  };
  if (result.coarsePointer && root.clientWidth === innerWidth && root.scrollWidth === innerWidth &&
      body.scrollWidth <= body.clientWidth && window.scrollX === 0 && blocks.length === 4 &&
      blocks.every(b => b.scroll > b.client && b.moved === 96 && b.overflowX === "auto")) {
    return result;
  }
  throw Error("Mobile overflow check failed: " + JSON.stringify(result));
})()
