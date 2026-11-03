import { createContext, useContext } from "react";

export const ChatContext = createContext<{ openChat: (message?: string) => void }>({ openChat: () => {} });
export const useChat = () => useContext(ChatContext);
