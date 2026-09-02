import apiClient from "./client";

export async function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/resume/upload", formData);
  return data;
}
