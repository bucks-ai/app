// Zod schema for the POST /api/auth/signup request body.

import { z } from "zod";

export const signupBodySchema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  // Matches Supabase Auth's own default minimum password length.
  password: z.string().min(6, "Password must be at least 6 characters."),
});

export type SignupBody = z.infer<typeof signupBodySchema>;
