#pragma once
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
namespace mirage::profile
{
struct StylePreferences
{
    std::vector<std::string> preferredStyles, preferredColors, avoidedColors, preferredCategories;
    void validate() const
    {
        for (const auto *list :
             {&preferredStyles, &preferredColors, &avoidedColors, &preferredCategories})
        {
            if (list->size() > 50)
                throw std::invalid_argument("too_many_preferences");
            std::set<std::string> seen;
            for (const auto &value : *list)
            {
                if (value.empty() || value.size() > 80 ||
                    value.find_first_not_of(" \t\r\n") == std::string::npos ||
                    value.find('\0') != std::string::npos || !seen.insert(value).second)
                    throw std::invalid_argument("invalid_or_duplicate_preference");
            }
        }
        std::set<std::string> avoided(avoidedColors.begin(), avoidedColors.end());
        for (const auto &color : preferredColors)
            if (avoided.count(color))
                throw std::invalid_argument("conflicting_color_preferences");
    }
};
} // namespace mirage::profile
