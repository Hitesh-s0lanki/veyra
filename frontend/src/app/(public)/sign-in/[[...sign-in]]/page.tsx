import { SignIn } from "@clerk/nextjs";
import { Suspense } from "react";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center px-4 py-10">
      <Suspense fallback={<p className="text-sm text-muted-foreground">Loading sign in...</p>}>
        <SignIn />
      </Suspense>
    </div>
  );
}
