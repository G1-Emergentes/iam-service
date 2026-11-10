#pragma once
#include "../application/IdentityProvider.h"
namespace mirage::auth
{
class SupabaseIdentityProvider final : public IdentityProvider
{
  public:
    void execute(IdentityOperation, Json::Value, std::string, Completion) const override;
};
} // namespace mirage::auth
