"use client";

import React, { FC, memo, useEffect, useState } from "react";

interface pageProps {}
const Child = memo(function ({ value }: { value: boolean }) {
  console.log(true);
  return <h1>hi</h1>;
});

const page: FC<pageProps> = ({}) => {
  const [value, setValue] = useState<number>(0);

  //   useEffect(() => {
  //     // setValue(value + 1);
  //     return () => setValue(value + 1);
  //   }, [value]);

  return (
    <div>
      <button
        onClick={
          () => setValue((prev) => prev + 1)
          //   setTimeout(() => {
          //     setValue(value + 1);
          //     setValue(value + 1);
          //     setValue(value + 1);
          //   }, 2000)
        }
      >
        click
      </button>
      <Child value={true} />
      <p>{value}</p>
    </div>
  );
};

export default page;
