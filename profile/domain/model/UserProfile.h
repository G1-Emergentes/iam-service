#pragma once
#include <optional>
#include <string>
namespace mirage::profile
{
struct UserProfile
{
    std::string id, userId, displayName;
    std::optional<std::string> birthDate, profileImageUrl, avatarReference;
    std::string createdAt, updatedAt;
};
} // namespace mirage::profile
