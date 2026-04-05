"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function PaperRootPage({ params }: { params: Promise<{ paper: string }> }) {
  const { paper } = use(params);
  const router = useRouter();
  useEffect(() => {
    router.replace(`/${paper}/sections`);
  }, [paper, router]);
  return null;
}
