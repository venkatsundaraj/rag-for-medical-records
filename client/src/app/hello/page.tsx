"use client";

import { FC, useEffect, useState } from "react";

interface pageProps {}

const page: FC<pageProps> = ({}) => {
  const [items, setItems] = useState<{ x: number; y: number }[]>([]);
  useEffect(() => {
    const handClick = function (e: PointerEvent) {
      const x = e.pageX;
      const y = e.pageY;

      setItems((prev) => [...prev, { x, y }]);
    };
    window.addEventListener("click", handClick);
  }, []);
  return (
    <div className="relative">
      {items.length
        ? items.map((item, i) => (
            <div
              key={i}
              style={{ top: `${item.y}px`, left: `${item.x}px` }}
              className="w-8 h-8 -translate-x-1/2 -translate-y-1/2 bg-red-600 absolute"
            />
          ))
        : null}
    </div>
  );
};

export default page;
