"use client";

import type { ComponentProps } from "react";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";

const ITEMS = [
  { label: "Result", href: "#result" },
  { label: "Method", href: "#method" },
  { label: "Replay", href: "#replay" },
  { label: "Real issues", href: "#real-issues" },
];

export const NavMenu = (props: ComponentProps<typeof NavigationMenu>) => (
  <NavigationMenu {...props}>
    <NavigationMenuList className="data-[orientation=vertical]:-ms-2 data-[orientation=vertical]:flex-col data-[orientation=vertical]:items-start data-[orientation=vertical]:justify-start">
      {ITEMS.map((item) => (
        <NavigationMenuItem key={item.href}>
          <NavigationMenuLink asChild className={navigationMenuTriggerStyle()}>
            <a href={item.href}>{item.label}</a>
          </NavigationMenuLink>
        </NavigationMenuItem>
      ))}
    </NavigationMenuList>
  </NavigationMenu>
);
